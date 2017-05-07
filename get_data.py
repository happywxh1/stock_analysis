#!/usr/bin/env python2

import urllib.request
import csv
import re
import pytz
import pandas as pd

from bs4 import BeautifulSoup
from datetime import datetime
from pandas.io.data import DataReader
import requests


def getSP500List():
    site_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    hdr = {'User-Agent': 'Mozilla/5.0'}
    req = urllib.request.Request(site_url, headers=hdr)
    page = urllib.request.urlopen(req)
    soup = BeautifulSoup(page)

    table = soup.find('table', {'class': 'wikitable sortable'})
    sector_tickers = dict()
    for row in table.findAll('tr'):
        col = row.findAll('td')
        if len(col) > 0:
            stock_symb = str(col[0].string.strip())
            stock_symb = stock_symb.replace('-', '')
            category = str(col[3].string.strip()).lower().replace(' ', '_')
            sector_tickers[stock_symb] = category
    return sector_tickers


RENAME = {"Gross Margin %": "Gross Margin %",
            "Earnings Per Share [A-Z]*": "EPS",
            "Free Cash Flow [A-Z]* Mil": "Free Cash Flow",
            "Revenue [A-Z]* Mil": "Revenue",
          "Net Income [A-Z]* Mil": "Net Income"
            }

class gradComanyStats(object):
    """
        Using morning star ajax call.
        Can only get one stock at a time.
    """
    def __init__(self):
        """ List of url parameters -- for url formation """
        self.base_url = 'http://financials.morningstar.com/ajax/exportKR2CSV.html?&callback=?&t='
        self.end_url = '&region=usa&culture=en-US&cur=&order=asc'
        self.url_additional_params = ''
        self.stock_list = []
        self.filter_list = []
        self.basic_attrs = []
        self.info_dict = {}
        self.yearly_data = {}

    def set_stock_list(self, list):
        self.stock_list = list

    def set_attr_list(self, list):
        self.basic_attrs = list

    def buildUrl(self, stock):
        url = self.base_url + stock + self.end_url
        return url

    def grad_attr(self, data):
        dict = {}
        #print(data.decode().split('\n'))
        csv_data = csv.reader(data.decode().split('\n'), delimiter=',')
        csv_list = list(csv_data)
        for attr in self.basic_attrs:
            for row in csv_list:
                if len(row) < 3: continue
                if re.search(attr, row[0]) != None:
                    l = []
                    for n in row[6:]:
                        # from 2016 - current
                        if n == '':
                            l.append(0)
                        else:
                            l.append(float(n.replace(',','')))
                    dict[RENAME[attr]] = l
                    break
        return dict

    def gradCompanyData(self):
        for s in self.stock_list:
            url = self.buildUrl(s)
            data = requests.get(url, stream=True)
            self.info_dict[s] = self.grad_attr(data.content)
        #print self.info_dict

    def gradStockPrice(self):
        # 5y stock price from 2012 - 2017
        # Note that some stock on market < 5y; so be careful
        for s in self.stock_list:
            if "Stock Price" not in self.info_dict[s]:
                self.info_dict[s]["Price"] = []
            url = "http://performance.morningstar.com/perform/Performance/stock/exportStockPrice.action?t={}&" \
                 "pd=5y&freq=a&sd=&ed=&pg=0&culture=en-US&order=asc".format(s)
            data = requests.get(url, stream=True)
            csv_data = csv.reader(data.content.decode().split('\n'), delimiter=',')
            for row in csv_data:
                if len(row)>5:
                    try:
                        # to avoid the float("Date) error
                        a = float(row[4])
                    except:
                        continue
                    # time; stock price; market price
                    #print row
                    try:
                        self.info_dict[s]["Price"].append([row[0], float(row[4]), float(row[4])*int(row[5].replace(',',''))])
                    except:
                        continue

    def organizeYearlyData(self):
        '''
        organize data by year in order of:
        Price(0); Market Price(1); P/E(2); Revenue(3); EPS(4); Net Income(5); Free Cash flow(6); Gross Margin(7);
         Revenue Growth(8); EPS Growth(9); Net Income Growth(10)
        '''
        for s in self.stock_list:
            info = self.info_dict[s]
            if "Revenue" not in info:
                self.filter(s)
                continue
            self.yearly_data[s] = {}
            for y in range(2012, 2018):
                l = [info["Revenue"][y-2012], info["EPS"][y-2012], info["Net Income"][y-2012], info["Free Cash Flow"][y-2012], info["Gross Margin %"][y-2012]]

                if 2017-y >= len(info["Price"]) or str(y) not in info["Price"][2017-y][0]:
                    l = [None, None, None] + l
                else:
                    price_l = info["Price"][2017-y]
                    eps = l[1]
                    l = [price_l[1], price_l[2], price_l[1]/eps if eps!=0 else 0] + l

                if y > 2012:
                    if(info["Revenue"][y-2012] != 0):
                        growth = (info["Revenue"][y-2012] - info["Revenue"][y-2013])/info["Revenue"][y-2012]
                        l.append(growth)
                    else:
                        l.append(None)
                    if info["EPS"][y-2012] != 0:
                        growth = (info["EPS"][y - 2012] - info["EPS"][y - 2013])/info["EPS"][y - 2012]
                        l.append(growth)
                    else:
                        l.append(None)
                    if info["Net Income"][y-2012] != 0:
                        growth = (info["Net Income"][y - 2012] - info["Net Income"][y - 2013])/info["Net Income"][y - 2012]
                        l.append(growth)
                    else:
                        l.append(None)
                self.yearly_data[s][str(y)] = l

    def filter(self, s):
        self.filter_list.append(s)
        del self.info_dict[s]
        return

    def hardCritia(self):
        '''
        Filter critia:
        1. Company price has to be > 1 billion
        2. Have to make profit, which means EPS > 0
        3. Free cash flow >= Revenue
        4. latest PE <= 20
        '''
        for s in self.stock_list:
            if s in self.filter_list:
                continue
            info = self.yearly_data[s]["2017"]
            if None in info:
                self.filter(s)
                continue;
            #print info
            if info[4]<=0 or info[1]<=1:
                self.filter(s)
            elif info[6] < info[5]:
                self.filter(s)
            # filter stock which PE>20 and PEG<1.2
            elif info[2]>50 or info[8]<0.05 or info[9]<=0 or info[10]<0:
                self.filter(s)
            elif not (info[9]>0): #and info2016[2]/info2016[9]<1.2):
                self.filter(s)
            elif (info[2]>20 and info[2]/info[10]/100>1.1):
                self.filter(s)
            else:
                if info[2]>20:
                    #print the high growth stock
                    print(s)

if __name__ == '__main__':
    pp = gradComanyStats()
    sp500 = getSP500List().keys()
    pp.set_stock_list(sp500)
    basic_attrs = ["Gross Margin %", "Earnings Per Share [A-Z]*", "Free Cash Flow [A-Z]* Mil", "Revenue [A-Z]* Mil", "Net Income [A-Z]* Mil"]
    pp.set_attr_list(basic_attrs)
    pp.gradCompanyData()
    pp.gradStockPrice()
    pp.organizeYearlyData()
    pp.hardCritia()
    print(pp.info_dict.keys())

