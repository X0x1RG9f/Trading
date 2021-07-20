#!/usr/bin/python3
# encoding: utf-8

############################################
#                                          #
# /!\ PYTHON 3 ONLY                        #
#                                          #
# ICHIMOKU CLOUDS Ludovic COURGNAUD        #
# 04-2020                                  #
#                                          #
# SENDS EMAILS FOR IMPORTANT EVENTS :      #
#    - Price above cloud                   #
#    - Price under cloud                   #
#    - Kijunsen Cross Tenkansen            #
#    - Kijunsen Cross Price                #
#                                          #
############################################

###################################################### IMPORTS #####################################################################
import requests
import pandas as pd
import os
import string
import sys
import urllib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import argparse
from datetime import datetime
from datetime import timezone
import numpy as np
import json
import time
import itertools

start_time = time.time()

###################################################### CONFIG ######################################################################
MARKETS			= ""

CONFIG			= ""
INTERVAL		= ""
DEBUG			= False
OUTPUT			= ""
RECHECK			= False
CLOUD_ONLY		= False

SMTP_SERVER		= ""
SMTP_PORT		= ""
SMTP_AUTH		= ""
RECIPIENTS		= ""

scores			= {}
closes			= {}

##################################################### FUNCTIONS ####################################################################

#
# Print with debug condition
#
def myprint(str):
	if DEBUG:
		print(str)

#
# Parse args from command line
#
def parse_args():
	global MARKETS

	global CONFIG
	global INTERVAL
	global DEBUG
	global OUTPUT
	global RM_VALUES
	global RECHECK
	global CLOUD_ONLY

	global SMTP_SERVER
	global SMTP_AUTH
	global SMTP_PORT
	global RECIPIENTS


	example_text = '''Examples:
 		python3 ichimoku.py -m MSFT -i 15m --txt
 		python3 ichimoku.py -f ./markets.txt --html --debug
 		python3 ichimoku.py -m 'MSFT, CS.PA' -r 'myemail@test.com' -a 'myemail@gmail.com:mypassword' '''

	parser = argparse.ArgumentParser(prog='./ichimoku.py', epilog=example_text,  formatter_class=argparse.RawDescriptionHelpFormatter)

	# Mandatory args
	parser.add_argument("-f",  "--markets-file", type=str, help="Input file containing markets to follow (one per line).")
	parser.add_argument("-m",  "--markets", type=str, help="Input string containing markets to follow (comma separated).")

	# Optional args
	parser.add_argument("-i",  "--interval", type=str, help="Interval of stock data to process. Default '1h'.", choices=['30m', '1h', '4h', '1d'], default="1h")
	parser.add_argument("-c",  "--config", type=str, help="Ichimoku settings. Default '9,26,52'.",  choices=['9,26,52', '7,22,44'], default='9,26,52')
	parser.add_argument("-d",  "--debug", help="Activate debug mode. Default 'False'.",  action='store_true', default=False)
	parser.add_argument("-o",  "--output", help="Results output mode.",  choices=['TXT', 'EMAIL', 'HTML'], default="TXT")
	parser.add_argument("-r",  "--remove-values", type=int, help="Number of values to be removed. Use for past analasys only. Default 0.", default=0)
	parser.add_argument("-n",  "--check-null", help="Perform second stock request if many null values. Default 'False'.",  action='store_true', default=False)
	parser.add_argument("-x",  "--cloud-only", help="Process only scores for Cloud Signals (Up / Above). Default 'False'.",  action='store_true', default=False)

	# Optional SMTP args
	parser.add_argument("-s",  "--smtp-server", type=str, help="SMTP Server from which notification will be sent. Default 'smtp.gmail.com'", default='smtp.gmail.com')
	parser.add_argument("-p",  "--smtp-port", type=int, help="SMTP Server port from which notification will be sent. Default '587'.", default=587)
	parser.add_argument("-a",  "--smtp-auth", type=str, help="SMTP Server credentials (login:password).")
	parser.add_argument("-t",  "--to", type=str, help="Email recipient(s) for notification ('a@a.com, b@b.com').")

	args = parser.parse_args()

	INTERVAL	= args.interval

	CONFIG		= args.config.replace(" ", "").split(',')
	mp		= map(int, CONFIG)
	CONFIG 		= list(mp)

	DEBUG		= args.debug
	OUTPUT		= args.output
	RM_VALUES	= args.remove_values
	RECHECK		= args.check_null
	CLOUD_ONLY	= args.cloud_only

	RECIPIENTS	= args.to
	SMTP_SERVER	= args.smtp_server
	SMTP_PORT	= args.smtp_port

	if (args.smtp_auth != None) :
		SMTP_AUTH	= args.smtp_auth.split(":")

	if (args.markets_file == None) and (args.markets == None):
		print("ERROR: At least one market or file should be provided as argument. ")
		sys.exit(0)

	if (args.markets_file != None):
		if not os.path.isfile(args.markets_file):
			print("ERROR: File '" + args.markets_file + "' not found.")
			sys.exit(0)
		else:
			with open(args.markets_file) as f:
				MARKETS = f.read().splitlines()
	else:
		MARKETS = args.markets.replace(' ', '').split(",")

	if (OUTPUT == "EMAIL") and ((RECIPIENTS == None) or (SMTP_SERVER == None) or (SMTP_AUTH == None)) :
		myprint("WARNING: MAIL output specified but no SMTP information provided and / or recipients. Defaulting to TXT output")
		OUTPUT = "TXT"

	myprint("INFO: OUTPUTING AS " + OUTPUT + "!")
	myprint("")



#
# Retrieve data from Yahoo Finance & return DataFrame
#
def get_quote_data(symbol, ntvl, iteration):
	rng = "2y"

	if (ntvl == "30m"):
		rng = "10d"
	if (ntvl == "1h"):
		rng = "4mo"
	if (ntvl == "4h"):
		ntvl = "1h"
		rng  = "4mo"

	headers = {
		'User-Agent': ''
	}

	res = requests.get('https://query1.finance.yahoo.com/v8/finance/chart/' + symbol + '?range=' + rng + '&interval=' + ntvl, headers=headers)
	data = res.json()

	myprint('GET QUOTE DATA : https://query1.finance.yahoo.com/v8/finance/chart/' + symbol + '?range=' + rng + '&interval=' + ntvl)

	if (data['chart']['result'] == None):
		myprint("ERROR: Market unknown! Passing...")
		return None

	body = data['chart']['result'][0]
	df = pd.DataFrame(body['indicators']['quote'][0])

	df['timestamp'] 	= body['timestamp']

	df['timezone']		= body['meta']['exchangeTimezoneName']
	df['exchange']		= body['meta']['exchangeName']

	df['KIJUNSEN'] 		= 0.0
	df['TENKANSEN'] 	= 0.0
	df['SSA']		= 0.0
	df['SSB'] 		= 0.0

	df['SIGNAL_X_PRC_CLD']	= 0
	df['SIGNAL_X_CHI_KIJ']	= 0
	df['SIGNAL_X_KIJ_TEN']	= 0
	df['SIGNAL_X_KIJ_PRC']	= 0
	df['SIGNAL_X_CHI_PRC']	= 0
	df['SIGNAL_X_CHI_SSB']	= 0

	df['SIGNAL_PRC_CLD']	= 0
	df['SIGNAL_CHI_KIJ']	= 0
	df['SIGNAL_KIJ_TEN']	= 0
	df['SIGNAL_KIJ_PRC']	= 0
	df['SIGNAL_CHI_PRC']	= 0
	df['SIGNAL_CHI_SSB']	= 0

	df['SIGNAL_RATIO_LONG']		= 0
	df['SIGNAL_RATIO_SHORT']	= 0

	pd.options.mode.chained_assignment = None
	pd.set_option('display.max_rows', None)

	# Checking for Null / Error values, excluding weekends
	for i in range (df.index[0], df.index[-1] + 1):
		if np.isnan(df['open'][i]) and (datetime.fromtimestamp(df['timestamp'][i]).weekday() < 6):
			if RECHECK:
				if (iteration <= 1):
					time.sleep(1)
					myprint("WARNING: Market has too many Null values for processing. Trying again...")
					df = get_quote_data(symbol, ntvl, iteration + 1)
					break
				else:
					myprint("WARNING: Market has too many Null values for processing. Maybe errors...")
					break
			else:
				myprint("WARNING: Market has too many Null values for processing. Maybe errors...")
				break


	if (iteration <=1 ):
		if (df['volume'][df.index[-1]] == 0):
			df = df[:-1]

		for i in range (0,RM_VALUES):
			df = df[:-1]

		df = df[-500:]
		df.dropna(inplace=True)
		df.reset_index(drop=True, inplace=True)

		if (len(df) <= int(CONFIG[2] * 1.5)):
			myprint("ERROR: Market has too few history for Ichimoku! Passing...")
			return None

	return df



#
# Transform a 1h dataframe into a 4h (Yahoo does not provide 4h's one)
#
def transform_four_hours(df):
	myprint("ENTERING H4 PROCESSING...")

	df_size = 130

	# Sequences for candle transformation (depends on markets)
	eu_sequence = [4,4,1]
	us_sequence = [3,4]
	#cr_sequence = [4,4,4,4,4,4]
	#mp_sequence = [4,4,4,4,4,4]

	sequence = ""

	if (df['timezone'][0].split('/')[0] == "Europe"):
		sequence = eu_sequence

	if (df['timezone'][0].split('/')[0] == "America") and (df['exchange'][0] != "CMX"):
		sequence = us_sequence

	if (sequence == ""):
		myprint("ERROR: Stock market not supported yet for H4 Ichimoku, PASSING.")
		return None

	dt = datetime.today()
	dt = datetime(dt.year, dt.month, dt.day)
	timestamp = dt.replace(tzinfo=timezone.utc).timestamp()

	today_candle = 0
	for i in range (len(df) - 15, len(df)):
		if (df['timestamp'][i] >= timestamp):
			today_candle += 1

	start_sequence	= 0
	start_candle 	= df.index[-1]

	# Process : How many candle do we have a remove at the end for correct H4 ?
	start_sequence = 0
	for i in range (0, len(sequence)):
		if today_candle >= np.sum(sequence[i:len(sequence)]):
			start_sequence = i
			start_candle = start_candle - (today_candle - np.sum(sequence[i:len(sequence)]))
			break

	avg_candle = np.sum(sequence) / len(sequence)

	# Insure we have sufficient values to trasnform H1 data to H4 data (80 rows min for ichimoku)
	if ((len(df) / avg_candle) <= df_size):
		myprint("ERROR: Market has too few history for H4 ichimoku! Passing...")
		return None

	df4 = pd.DataFrame(columns=list(df.columns), index=[x for x in range(0, df_size)])

	df4['timezone']		= df['timezone'][0]
	df4['exchange']		= df['exchange'][0]

	df4['KIJUNSEN'] 	= 0.0
	df4['TENKANSEN'] 	= 0.0
	df4['SSA']		= 0.0
	df4['SSB'] 		= 0.0

	df4['SIGNAL_X_PRC_CLD']	= 0
	df4['SIGNAL_X_CHI_KIJ']	= 0
	df4['SIGNAL_X_KIJ_TEN']	= 0
	df4['SIGNAL_X_KIJ_PRC']	= 0
	df4['SIGNAL_X_CHI_PRC']	= 0
	df4['SIGNAL_X_CHI_SSB']	= 0

	df4['SIGNAL_PRC_CLD']	= 0
	df4['SIGNAL_CHI_KIJ']	= 0
	df4['SIGNAL_KIJ_TEN']	= 0
	df4['SIGNAL_KIJ_PRC']	= 0
	df4['SIGNAL_CHI_PRC']	= 0
	df4['SIGNAL_CHI_SSB']	= 0

	df4['SIGNAL_RATIO_LONG']	= 0
	df4['SIGNAL_RATIO_SHORT']	= 0

	cpt1 = start_candle
	cpt2 = 1
	while (df_size-cpt2 >= 0):
		for i in range (0, len(sequence)):
			if (i >= start_sequence):
				s = sequence[i]
				if sequence[i] > 1 :
					df4['low'][df_size-cpt2]         =  np.min(df['low'][cpt1-s+1:cpt1+1])
					df4['high'][df_size-cpt2]        =  np.max(df['high'][cpt1-s+1:cpt1+1])
					df4['volume'][df_size-cpt2]      =  np.sum(df['volume'][cpt1-s+1:cpt1+1])
					df4['open'][df_size-cpt2]        =  df['open'][cpt1-s+1]
					df4['close'][df_size-cpt2]       =  df['close'][cpt1]
					df4['timestamp'][df_size-cpt2]   =  df['timestamp'][cpt1-s+1]
				else:
					df4['low'][df_size-cpt2]         =  df['low'][cpt1]
					df4['high'][df_size-cpt2]        =  df['high'][cpt1]
					df4['volume'][df_size-cpt2]      =  df['volume'][cpt1]
					df4['open'][df_size-cpt2]        =  df['open'][cpt1]
					df4['close'][df_size-cpt2]       =  df['close'][cpt1]
					df4['timestamp'][df_size-cpt2]   =  df['timestamp'][cpt1]


				cpt1 -= s
				cpt2 += 1
		start_sequence = 0

	for i in range (0,RM_VALUES):
		df4 = df4[:-1]

	return df4

#
# Sends Email to recipients
#
def send_email(msg):
	myprint("SENDING EMAIL...")

	sender = "Trading Server"

	message = MIMEMultipart("alternative")
	message["Subject"] = "Trading Opportunities (" +  datetime.now().strftime('%d/%m %H:%M')  + ") !"
	message["From"] = "Trading Server"
	message["To"] = RECIPIENTS

	message.attach(MIMEText(msg,"html"))

	server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
	server.ehlo()
	server.starttls()
	server.ehlo()
	server.login(SMTP_AUTH[0], SMTP_AUTH[1])
	server.sendmail( sender, RECIPIENTS, message.as_string() )


#
# Process Ichimoku Cloud data from received Yahoo DataFrame
#
def processIchimoku(df):
	# NOT IMPORTANT PROCESSING ALL DATA, ONLY FEW WINDOWS NECESSARY
	for i in range (df.index[-1] - 8, df.index[-1] + 1 ):
		# KIJUN SEN & TENKAN SEN
		df['KIJUNSEN'][i]		= (np.max(df['high'][i-(CONFIG[1]-1):i+1]) + np.min(df['low'][i-(CONFIG[1]-1):i+1]) ) / 2
		df['TENKANSEN'][i]		= (np.max(df['high'][i-(CONFIG[0]-1):i+1]) + np.min(df['low'][i-(CONFIG[0]-1):i+1]) ) / 2

		df['KIJUNSEN'][i-CONFIG[1]]	= (np.max(df['high'][(i-CONFIG[1])-(CONFIG[1]-1):i-CONFIG[1]+1]) + np.min(df['low'][(i-CONFIG[1])-(CONFIG[1]-1):i-CONFIG[1]+1]) ) / 2
		df['TENKANSEN'][i-CONFIG[1]]	= (np.max(df['high'][(i-CONFIG[1])-(CONFIG[0]-1):i-CONFIG[1]+1]) + np.min(df['low'][(i-CONFIG[1])-(CONFIG[0]-1):i-CONFIG[1]+1]) ) / 2

		df['KIJUNSEN'][i-CONFIG[1]-CONFIG[1]]	= (np.max(df['high'][(i-CONFIG[1]-CONFIG[1])-(CONFIG[1]-1):i-CONFIG[1]-CONFIG[1]+1]) + np.min(df['low'][(i-CONFIG[1]-CONFIG[1])-(CONFIG[1]-1):i-CONFIG[1]-CONFIG[1]+1]) ) / 2
		df['TENKANSEN'][i-CONFIG[1]-CONFIG[1]]	= (np.max(df['high'][(i-CONFIG[1]-CONFIG[1])-(CONFIG[0]-1):i-CONFIG[1]-CONFIG[1]+1]) + np.min(df['low'][(i-CONFIG[1]-CONFIG[1])-(CONFIG[0]-1):i-CONFIG[1]-CONFIG[1]+1]) ) / 2

		# SSA & SSB
		df['SSA'][i-CONFIG[1]] 	= (df['KIJUNSEN'][i-CONFIG[1]-CONFIG[1]] + df['TENKANSEN'][i-CONFIG[1]-CONFIG[1]]) / 2
		df['SSB'][i-CONFIG[1]] 	= (np.max(df['high'][(i-CONFIG[1]-CONFIG[1])-(CONFIG[2]-1):(i-CONFIG[1]-CONFIG[1]+1)])  + np.min(df['low'][(i-CONFIG[1]-CONFIG[1])-(CONFIG[2]-1):(i-CONFIG[1]-CONFIG[1]+1)])  ) / 2

		df['SSA'][i] = (df['KIJUNSEN'][i-CONFIG[1]] + df['TENKANSEN'][i-CONFIG[1]]) / 2
		df['SSB'][i] = (np.max(df['high'][(i-CONFIG[1])-(CONFIG[2]-1):(i-CONFIG[1])+1])  + np.min(df['low'][(i-CONFIG[1])-(CONFIG[2]-1):(i-CONFIG[1])+1])  ) / 2


	for i in range (df.index[-1] - 7, df.index[-1] + 1):
		# Are we in a bearish trend (SELL)
		if ( (df['close'][i] < df['SSA'][i]) and (df['close'][i] < df['SSB'][i]) ):
			if ( (df['open'][i] < df['SSA'][i]) or (df['open'][i] < df['SSB'][i]) ):
				df['SIGNAL_PRC_CLD'][i] = -1

		# Are we in a bullish trend (BUY)
		if ( (df['close'][i] > df['SSA'][i]) and (df['close'][i] > df['SSB'][i]) ):
			if ( (df['open'][i] > df['SSA'][i]) or (df['open'][i] > df['SSB'][i]) ):
				df['SIGNAL_PRC_CLD'][i] = 1

		# Do we have a cloud buying signal (price going above cloud) ?
		if ( (df['SIGNAL_PRC_CLD'][i] == 1 ) and (df['SIGNAL_PRC_CLD'][i-1] != 1 ) ):
			df['SIGNAL_X_PRC_CLD'][i] = 1

		# Do we have a cloud selling signal (price going under cloud) ?
		if ( (df['SIGNAL_PRC_CLD'][i] == -1 ) and (df['SIGNAL_PRC_CLD'][i-1] != -1 ) ):
			df['SIGNAL_X_PRC_CLD'][i] = -1

		# Is Chikou crossing Kijun ?
		if ((df['close'][i-1] <= df['KIJUNSEN'][i-(CONFIG[1]+1)]) and (df['close'][i] >= df['KIJUNSEN'][i-CONFIG[1]]) ):  df['SIGNAL_X_CHI_KIJ'][i] = 1
		if ((df['close'][i-1] >= df['KIJUNSEN'][i-(CONFIG[1]+1)]) and (df['close'][i] <= df['KIJUNSEN'][i-CONFIG[1]]) ):  df['SIGNAL_X_CHI_KIJ'][i] = -1

		# Is Kijun crossing Tenkan ?
		if (df['KIJUNSEN'][i-1] >= df['TENKANSEN'][i-1]) and (df['KIJUNSEN'][i] <  df['TENKANSEN'][i]): df['SIGNAL_X_KIJ_TEN'][i] = 1
		if (df['KIJUNSEN'][i-1] <= df['TENKANSEN'][i-1]) and (df['KIJUNSEN'][i] >  df['TENKANSEN'][i]): df['SIGNAL_X_KIJ_TEN'][i] = -1

		# Is Kijun crossing Price ?
		if (df['KIJUNSEN'][i-1] >= df['close'][i-1] and df['KIJUNSEN'][i] <= df['close'][i]):	df['SIGNAL_X_KIJ_PRC'][i] = 1
		if (df['KIJUNSEN'][i-1] <= df['close'][i-1] and df['KIJUNSEN'][i] >= df['close'][i]):	df['SIGNAL_X_KIJ_PRC'][i] = -1

		# Is Chikou crossing SSB ?
		if (df['SSB'][i-(CONFIG[1]+1)] >= df['close'][i-1]) and (df['SSB'][i-CONFIG[1]] < df['close'][i]) : df['SIGNAL_X_CHI_SSB'][i] = 1
		if (df['SSB'][i-(CONFIG[1]+1)] <= df['close'][i-1]) and (df['SSB'][i-CONFIG[1]] > df['close'][i]) : df['SIGNAL_X_CHI_SSB'][i] = -1

		# Is Chikou crossing Price ?
		if (df['close'][i-(CONFIG[1]+1)] >= df['close'][i-1]) and (df['close'][i-CONFIG[1]] < df['close'][i]) : df['SIGNAL_X_CHI_PRC'][i] = 1
		if (df['close'][i-(CONFIG[1]+1)] <= df['close'][i-1]) and (df['close'][i-CONFIG[1]] > df['close'][i]) : df['SIGNAL_X_CHI_PRC'][i] = -1


		# Is Price under of above Kijun ?
		if (df['KIJUNSEN'][i] < df['close'][i]):	df['SIGNAL_KIJ_PRC'][i] = 1
		if (df['KIJUNSEN'][i] > df['close'][i]):	df['SIGNAL_KIJ_PRC'][i] = -1

		# Is Chikou under or above Price ?
		if (df['close'][i] > df['close'][i-CONFIG[1]]):	df['SIGNAL_CHI_PRC'][i] = 1
		if (df['close'][i] < df['close'][i-CONFIG[1]]):	df['SIGNAL_CHI_PRC'][i] = -1

		# Is Chikou under or above Kijun ?
		if (df['close'][i] > df['KIJUNSEN'][i-CONFIG[1]]):  df['SIGNAL_CHI_KIJ'][i] = 1
		if (df['close'][i] < df['KIJUNSEN'][i-CONFIG[1]]):  df['SIGNAL_CHI_KIJ'][i] = -1

		# Is Kijun under or above Tenkan ?
		if (df['KIJUNSEN'][i] > df['TENKANSEN'][i]):  df['SIGNAL_KIJ_TEN'][i] = -1
		if (df['KIJUNSEN'][i] < df['TENKANSEN'][i]):  df['SIGNAL_KIJ_TEN'][i] = 1

		# Is Chikou under or above SSB ?
		if (df['close'][i] > df['SSB'][i-CONFIG[1]]):  df['SIGNAL_CHI_SSB'][i] = 1
		if (df['close'][i] < df['SSB'][i-CONFIG[1]]):  df['SIGNAL_CHI_SSB'][i] = -1

		# Processing percent of SHORT and LONG signals
		nodes = {}
		nodes['A'] = df['SIGNAL_PRC_CLD'][i]
		nodes['B'] = df['SIGNAL_KIJ_PRC'][i]
		nodes['C'] = df['SIGNAL_CHI_PRC'][i]
		nodes['D'] = df['SIGNAL_CHI_KIJ'][i]
		nodes['E'] = df['SIGNAL_KIJ_TEN'][i]
		nodes['F'] = df['SIGNAL_CHI_SSB'][i]

		for node in nodes:
			if (nodes[node] == 1):
				df['SIGNAL_RATIO_LONG'][i] = df['SIGNAL_RATIO_LONG'][i] + 1
			if (nodes[node] == -1):
				df['SIGNAL_RATIO_SHORT'][i] = df['SIGNAL_RATIO_SHORT'][i] - 1

		df['SIGNAL_RATIO_LONG'][i] = df['SIGNAL_RATIO_LONG'][i] * 100 / 6
		df['SIGNAL_RATIO_SHORT'][i] = df['SIGNAL_RATIO_SHORT'][i] * 100 / 6

	return df

#
# Process score for DataFrame
#
def process_score(df):
	myprint("PROCESSING SCORE...")

	# Processing scores for each symbol
	nodes 		= {}
	histo_scores	= [0,0]
	cloud_signal	= False

	nodes['A'] = df['SIGNAL_X_PRC_CLD'][df.index[-1]]
	nodes['B'] = df['SIGNAL_X_KIJ_PRC'][df.index[-1]]
	nodes['C'] = df['SIGNAL_X_CHI_PRC'][df.index[-1]]
	nodes['D'] = df['SIGNAL_X_CHI_KIJ'][df.index[-1]]
	nodes['E'] = df['SIGNAL_X_KIJ_TEN'][df.index[-1]]
	nodes['F'] = df['SIGNAL_X_CHI_SSB'][df.index[-1]]

	sum_nodes_long = 0
	sum_nodes_shrt = 0

	for node in nodes:
		if (nodes[node] == 1):
			sum_nodes_long = sum_nodes_long + 1
		if (nodes[node] == -1):
			sum_nodes_shrt = sum_nodes_shrt + 1

	# We don't want to keep inside cloud signals
	if (df['SIGNAL_PRC_CLD'][df.index[-1]] != 0):
		# We want to remove contradictory signals
		if (sum_nodes_long >= 1) and (sum_nodes_shrt == 0):
			# We don't want to receive cloud signal if not confirmed by Chikou
			if (sum_nodes_long == 1) and (nodes['A'] == 1) and (df['SIGNAL_CHI_SSB'][df.index[-1]] != 1):
				myprint("Cloud signal received but not confirmed by Chikou !")
				return 0

			# We don't want to get false signals from Chikou (bounces, etc.)
			if ((sum_nodes_long == 1) and ((nodes['C'] == 1) or (nodes['D'] == 1) or (nodes['F'] == 1))):
				if (df['SIGNAL_X_CHI_PRC'][df.index[-1] - 1] == -1) or (df['SIGNAL_X_CHI_PRC'][df.index[-1] - 2] == -1):
					return 0
				if (df['SIGNAL_X_CHI_KIJ'][df.index[-1] - 1] == -1) or (df['SIGNAL_X_CHI_KIJ'][df.index[-1] - 2] == -1):
					return 0
				if (df['SIGNAL_X_CHI_SSB'][df.index[-1] - 1] == -1) or (df['SIGNAL_X_CHI_SSB'][df.index[-1] - 2] == -1):
					return 0

			# We don't want to buy if prices are under Kijun
			if (df['SIGNAL_KIJ_PRC'][df.index[-1]] != 1):
				myprint("Long signal received but not confirmed by Kijun !")
				return 0

			return df['SIGNAL_RATIO_LONG'][df.index[-1]]

		if (sum_nodes_shrt >= 1) and (sum_nodes_long == 0):
			# We don't want to receive cloud signal if not confirmed by Chikou
			if (sum_nodes_shrt == 1) and (nodes['A'] == -1) and (df['SIGNAL_CHI_SSB'][df.index[-1]] != -1):
				myprint("Cloud signal received but not confirmed by Chikou !")
				return 0

			# We don't want to get false signals from Chikou (bounces, etc.)
			if ((sum_nodes_shrt == 1) and ((nodes['C'] == -1) or (nodes['D'] == -1) or (nodes['F'] == -1))):
				if (df['SIGNAL_X_CHI_PRC'][df.index[-1] - 1] == 1) or (df['SIGNAL_X_CHI_PRC'][df.index[-1] - 2] == 1):
					return 0
				if (df['SIGNAL_X_CHI_KIJ'][df.index[-1] - 1] == 1) or (df['SIGNAL_X_CHI_KIJ'][df.index[-1] - 2] == 1):
					return 0
				if (df['SIGNAL_X_CHI_SSB'][df.index[-1] - 1] == 1) or (df['SIGNAL_X_CHI_SSB'][df.index[-1] - 2] == 1):
					return 0

			# We don't want to buy if prices are under Kijun
			if (df['SIGNAL_KIJ_PRC'][df.index[-1]] != -1):
				myprint("Long signal received but not confirmed by Kijun !")
				return 0

			return df['SIGNAL_RATIO_SHORT'][df.index[-1]]
	else:
		myprint("Signal Received but prices in cloud !")

	return 0


#
# Write Email with correct values taken from DataFrame
#
def write_email(scores, closes):
	myprint("BUILDING MESSAGE...")

	if (OUTPUT == "TXT"):
		MSG		= "SIGNALS " + INTERVAL + "\n\n"
		BUY_MSG		= "LONG :\n"
		SELL_MSG 	= "SHORT :\n"
		CLSEB_MSG 	= "CLOSE LONG :\n"
		CLSES_MSG 	= "CLOSE SHORT :\n"
	else :
		MSG		= "<html><body>SIGNALS " + INTERVAL + "<br/><br/>"
		BUY_MSG		= "<span style='color:green'><b>LONG :</b></span><br/><ul>"
		SELL_MSG 	= "<span style='color:red'><b>SHORT :</b></span><br/><ul>"
		CLSEB_MSG 	= "<span style='color:orange'><b>CLOSE LONG :</b></span><br/><ul>"
		CLSES_MSG 	= "<span style='color:orange'><b>CLOSE SHORT :</b></span><br/><ul>"

	buy	= False
	sell	= False
	close_b	= False
	close_s	= False

	table = sorted(scores.items(), key=lambda x: x[1], reverse=True)
	for score in table:
		if (score[1] > 66):
			buy = True
			if (OUTPUT == "TXT"):
				BUY_MSG = BUY_MSG + "\t- " + score[0] + " : " + str(int(score[1])) + "%\n"
			else:
				BUY_MSG = BUY_MSG + "<li><span style='color:green'><b>" + score[0] + " : " + str(int(score[1])) + "%</b></span></li>"


	table = sorted(scores.items(), key=lambda x: x[1])
	for score in table:
		if (score[1] < -66):
			sell = True
			if (OUTPUT == "TXT"):
				SELL_MSG = SELL_MSG + "\t- " + score[0] + " : " + str(int(score[1])) + "%\n"
			else:
				SELL_MSG = SELL_MSG + "<li><span style='color:red'><b>" + score[0] + " : " + str(int(score[1])) + "%</b></span></li>"

	closes = sorted(closes.items(), key=lambda x: x[0])
	for cls in closes:
		if (OUTPUT == "TXT"):
			tmpmess = "\t- " + cls[0] + " : " + str(int(cls[1])) + "%\n"
		else:
			tmpmess ="<li><span style='color:orange'><b>" + cls[0] + " : " + str(int(cls[1])) + "%</b></span></li>"

		if (cls[1] == 1):
			if os.path.isfile("./MYTRADES/" + cls[0] + "_" + INTERVAL + "_long"):
				close_b = True
				CLSEB_MSG = CLSEB_MSG + tmpmess
		else:
			if os.path.isfile("./MYTRADES/" + cls[0] + "_" + INTERVAL + "_short"):
				close_s = True
				CLSES_MSG = CLSES_MSG + tmpmess

	if (OUTPUT != "TXT"):
		if (buy):
			MSG = MSG + BUY_MSG + "</ul><br/>"
		if (sell):
			MSG = MSG + SELL_MSG + "</ul><br/>"
		if (close_b):
			MSG = MSG + CLSEB_MSG + "</ul><br/>"
		if (close_s):
			MSG = MSG + CLSES_MSG + "</ul><br/>"
	else:
		if (buy):
			MSG = MSG + BUY_MSG + "\n"
		if (sell):
			MSG = MSG + SELL_MSG + "\n"
		if (close_b):
			MSG = MSG + CLSEB_MSG + "\n"
		if (close_s):
			MSG = MSG + CLSES_MSG + "\n"

	if (buy or sell or close_b or close_s):
		return MSG
	else:
		return None


def process_symbol(symbol):
	global scores
	global closes

	myprint("SYMBOL: " + symbol)

	df 	= get_quote_data(symbol, INTERVAL, 1)

	symbol = symbol.rstrip().replace(".","_").replace("-","_").replace("/","_")

	if (INTERVAL == "4h"):
		df = transform_four_hours(df)

	if (df is None) :
		return

	df 	= processIchimoku(df)
	score   = process_score(df)

	pd.set_option('display.max_rows', 25)
	myprint(df[['timestamp', 'open', 'close', 'SIGNAL_KIJ_PRC', 'SIGNAL_X_PRC_CLD', 'SIGNAL_X_CHI_KIJ', 'SIGNAL_X_KIJ_TEN', 'SIGNAL_X_KIJ_PRC', 'SIGNAL_X_CHI_PRC', 'SIGNAL_CHI_SSB', 'SIGNAL_RATIO_LONG', 'SIGNAL_RATIO_SHORT']])
	pd.set_option('display.max_rows', None)

	f = open('test.csv', 'a')
	if (score > 66):
		f.write("LONG,"  + str(df['timestamp'][len(df)-1]) + "," + str(symbol) + "," + str(int(score)) + ',' + str(df['close'][len(df)-1]) + "\n")
	if (score < -66):
		f.write("SHORT,"  + str(df['timestamp'][len(df)-1]) + "," + str(symbol) + "," + str(int(score)) + ',' + str(df['close'][len(df)-1]) + "\n")

	f.close()
	scores[symbol]  = score


#
# Main function
#
def main():
	global scores
	global closes

	# For each market, retrieve, process and write in email
	for symbol in MARKETS:
		process_symbol(symbol)

	# Write & send message
	MSG = write_email(scores, closes)
	if (MSG != None):
		if (OUTPUT == "EMAIL"):
			send_email(MSG + "</body></html>")
		else:
			print(MSG)


################################################### START PROGRAM ##################################################################
parse_args()
main()
myprint("--- %s seconds ---" % (time.time() - start_time))
