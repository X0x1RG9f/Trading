#!/usr/bin/env python3
# encoding: utf-8

# MACD Ludovic COURGNAUD 2020

import requests
import pandas as pd
from datetime import datetime
import os
import string
import sys
import sqlalchemy as sqla
from array import *
import time

INTERVAL = sys.argv[2]
RANGE = "6mo"
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://trading:Trading123*@192.168.1.16:3307/trading'


def get_quote_data(symbol, data_range=RANGE, data_interval=INTERVAL):
	res = requests.get('https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={data_range}&interval={data_interval}'.format(**locals()))
	data = res.json()

	body = data['chart']['result'][0]
	#dt = pd.Series(body['timestamp'])
	df = pd.DataFrame(body['indicators']['quote'][0]) #, index=dt)
	df['timestamp'] = body['timestamp']

	return df


def createMACD(df):
	df['E26'] = pd.Series.ewm(df['close'], span=26, adjust=False).mean()
	df['E12'] = pd.Series.ewm(df['close'], span=12, adjust=False).mean()
	df['MACD'] = df['E12'] - df['E26']
	df['SIGNAL'] = df['MACD'].ewm(span=9, adjust=False).mean()
	df['DIFF_SIGNAL'] = df['MACD'] - df['SIGNAL']
	df['EXPORT_TIME'] = time.time()
	return df

def connect_db():
	#return sqla.create_engine(SQLALCHEMY_DATABASE_URI, echo=False)
	return sqla.create_engine('sqlite:///:memory:', echo=False)

def insert_db(engine, table_name, df):
	df.to_sql(name=table_name,con=engine, if_exists='replace')

def main():
	engine = connect_db()
	now = datetime.now()
	mytime = now.strftime('%Y-%m-%d %H:%M:%S')

	# Populate DB
	f = open(sys.argv[1])
	for line in f:
		table_name = line.rstrip().replace(".","_").replace("-","_").replace("/","_")
		df = get_quote_data(line.rstrip())
		createMACD(df)
		insert_db(engine, table_name, df)
	f.close()

	# Process DB
	f = open(sys.argv[1])
	for line in f:
		table_name = line.rstrip().replace(".","_").replace("-","_").replace("/","_")

		result = engine.execute('SELECT `DIFF_SIGNAL` FROM `' + table_name + '` WHERE `index` >= (SELECT MAX(`index`)-2 FROM `' + table_name + '`);')
		id = 0
		diff_signals = {}

		for row in result:
			diff_signals[id] = row['DIFF_SIGNAL']
			id = id + 1

		if ((diff_signals[0] > 0) and (diff_signals[1] < 0)) or ((diff_signals[0] > 0) and (diff_signals[2] < 0)) or ((diff_signals[1] > 0) and (diff_signals[2] < 0)) :
			requests.get("https://platform.clickatell.com/messages/http/send?apiKey=z2HH5XMwTQqc2P33R_w4FQ%3D%3D&to=33677352115&content=" + mytime + " : VENDRE+(+" + sys.argv[3] + ")+:+" + table_name)

		if ((diff_signals[0] < 0) and (diff_signals[1] > 0)) or ((diff_signals[0] < 0) and (diff_signals[2] > 0)) or ((diff_signals[1] < 0) and (diff_signals[2] > 0)):
			requests.get("https://platform.clickatell.com/messages/http/send?apiKey=z2HH5XMwTQqc2P33R_w4FQ%3D%3D&to=33677352115&content=" + mytime + " : ACHETER+(+" + sys.argv[3] + ")+:+" + table_name)

	f.close()

main()
