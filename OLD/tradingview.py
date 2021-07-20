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
import pdftotext
import pdfkit
import urllib.parse
import signal
from contextlib import contextmanager

directory = "/home/ludo/Bureau/tradingview/"
intervals = ["1h", "4h", "1D"]

now = datetime.now()
mytime = now.strftime('%Y-%m-%d %H:%M:%S')


class TimeoutException(Exception): pass

@contextmanager
def time_limit(seconds):
	def signal_handler(signum, frame):
		raise TimeoutException
	signal.signal(signal.SIGALRM, signal_handler)
	signal.alarm(seconds)
	try:
		yield
	finally:
		signal.alarm(0)

def get_symbol_value(symbol, interval, cpt):
	#print(symbol)
	options={'javascript-delay': '1500', 'quiet':''}
	#options={'javascript-delay': '1200'}
	symbol = urllib.parse.quote(symbol.rstrip())
	url = "https://s.tradingview.com/embed-widget/technical-analysis/?locale=en#%7B%22interval%22%3A%22" + interval + "%22%2C%22width%22%3A%22425%22%2C%22isTransparent%22%3Atrue%2C%22height%22%3A%22450%22%2C%22symbol%22%3A%22" + symbol + "%22%2C%22showIntervalTabs%22%3Atrue%2C%22colorTheme%22%3A%22light%22%2C%22utm_source%22%3A%22192.168.1.16%22%2C%22utm_medium%22%3A%22widget%22%2C%22utm_campaign%22%3A%22technical-analysis%22%7D"
	try:
		with time_limit(5):
			pdfkit.from_url(url, 'tmp.pdf', options=options)
			with open("tmp.pdf", "rb") as f:
				pdf = pdftotext.PDF(f)

			os.remove("tmp.pdf")
	except TimeoutException:
		if (cpt < 3):
			return get_symbol_value(symbol, interval, cpt + 1)
		else:
			return ""

	return pdf[0].split()[-6:-3]


def get_symbol_values(symbol):
	res = "<tr><td>" + symbol + "</td>"

	for i in intervals :
		values = get_symbol_value(symbol, i, 1)

		if (len(values) == 0) or (values == "") :
			res = res + "<td align=center>ERROR</td>"
			continue

		sell	 = int(values[0])
		neutral	 = int(values[1])
		buy	 = int(values[2])
		total	 = sell + neutral + buy

		sell 	= int(sell / total * 100)
		neutral = int(neutral / total * 100)
		buy 	= int(buy / total * 100)

		if (sell > 75):
			res = res + "<td align=center>STRONG SELL (" + str(sell) + "%)</td>"
			continue

		if (buy > 75):
			res = res + "<td align=center>STRONG BUY (" + str(buy) + "%)</td>"
			continue

		if (abs(buy - sell) < 15):
			res = res +  "<td align=center>NEUTRAL</td>"
			continue

		if (neutral > 50):
			res = res +  "<td align=center>NEUTRAL</td>"
			continue

		if (sell > buy):
			res = res + "<td align=center>SELL (" + str(sell) + "%)</td>"
			continue

		if (buy > sell):
			res = res + "<td align=center>BUY (" + str(buy) + "%)</td>"
			continue

	return  res + "</tr>"


def loop_stock(stock):
	res = ""

	f = open(directory + stock + "_market.txt")
	for line in f :
		res = res + get_symbol_values(line)

	return res


def build_html():
	html = ""

	html = html +	"""	<!doctype html>

				<html lang="en">
				<head>
					<meta charset="utf-8">

					<title>Trading Stats LCO</title>

					<meta name="viewport" content="width=device-width, initial-scale=1">
					<link rel="stylesheet" type="text/css" href="//cdn.datatables.net/1.10.20/css/jquery.dataTables.min.css"/>
					<script type="text/javascript" src="https://code.jquery.com/jquery-3.3.1.js"></script>
					<script type="text/javascript" src="//cdn.datatables.net/1.10.20/js/jquery.dataTables.min.js"></script>

					<style>
						table.dataTable thead .sorting:after,
						table.dataTable thead .sorting:before,
						table.dataTable thead .sorting_asc:after,
						table.dataTable thead .sorting_asc:before,
						table.dataTable thead .sorting_asc_disabled:after,
						table.dataTable thead .sorting_asc_disabled:before,
						table.dataTable thead .sorting_desc:after,
						table.dataTable thead .sorting_desc:before,
						table.dataTable thead .sorting_desc_disabled:after,
						table.dataTable thead .sorting_desc_disabled:before {
							bottom: .5em;
						}
					</style>
				</head>

				<body> Generated : 
			"""
	html = html + mytime
	html = html + 	"""		<br />
					<table id="example" class="display" style="width:100%">
						<thead>
							<tr>
								<th>Name</th><th>1H</th><th>4H</th><th>1D</th>
							</tr>
						</thead>
						<tbody>

			"""

	html = html + loop_stock("eu")
	html = html + loop_stock("us")
	html = html + loop_stock("cr")

	html = html +	"""
						</tfoot>
					</table>
					<script>
						$(document).ready(function() {
							$('#example').DataTable();
						} );
					</script>
				</body>
				</html>
			"""
	return html



def main():
	html = build_html()
	file = open("/var/www/html/trading.html","w")
	file.write(html)
	file.close()

main()
