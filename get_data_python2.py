#!/usr/bin/env python2

import urllib2
from collections import namedtuple
import datetime

from bs4 import BeautifulSoup
from network_request import FinancialDataRequester

Stock = namedtuple('Stock', 'symbol, name, category')

def getSP500List():
    site_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    hdr = {'User-Agent': 'Mozilla/5.0'}
    req = urllib2.Request(site_url, headers=hdr)
    page = urllib2.urlopen(req)
    soup = BeautifulSoup(page)

    table = soup.find('table', {'class': 'wikitable sortable'})
    sector_tickers = []
    for row in table.findAll('tr'):
        col = row.findAll('td')
        if len(col) > 0:
            symb = col[0].text.strip()
            name = str(col[1].string.strip())
            name = name.replace('-', '')
            category = str(col[3].string.strip()).lower().replace(' ', '_')
            sector_tickers.append(Stock(symbol=symb, name=name, category=category))
    return sector_tickers


class StocksStatsFetcher(object):

    def __init__(self, stock_list, data_requester):
        """ List of url parameters -- for url formation """
        self.stock_list = stock_list
        self.info_dict = {}
        self.data_requester = data_requester
        self.high_growth_list = []
        self.qualify_list = []

    def check_stock_financials(self):
        self.__gradCompanyData()
        self.qualify_list = [s for s in self.stock_list if self.__check_stock_qualification(s) ]

    def qualified_stocks(self):
        return [str(s) for s in self.qualify_list]

    def high_growth_stocks(self):
        return [str(s) for s in self.high_growth_list]

    def __gradCompanyData(self):
        for s in self.stock_list:
            symb = s.symbol
            self.info_dict[symb] = self.data_requester.requestStockData(symb)
        # print self.info_dict

    def __check_stock_qualification(self, stock):
        '''
        Filter critia:
            1. Company price has to be > 1 billion
            2. Have to make profit, which means EPS > 0
            3. Free cash flow >= Revenue
            4. latest PE <= 20
        '''
        symbol = stock.symbol
        if self.info_dict[symbol] is None:
            return False
        if self.info_dict[symbol]["Capital"] <= 1000000000:
            return False
        financials = self.info_dict[symbol]["Financials"]

        now = datetime.datetime.now()
        chosen_year = str(int(now.year) - 1)
        if chosen_year not in financials:
            print("no financials available for chose year %s of stock %s" % (chosen_year, symbol))
            return

        print symbol, financials
        #company has to make profit
        if financials["TTM"].eps <=0 or financials[chosen_year].eps <=0:
            return False

        # company cash flow much be larger than its net income
        if financials["TTM"].free_cash_flow < financials["TTM"].net_income or \
                        financials["TTM"].free_cash_flow < financials["TTM"].net_income:
            return False
        if financials[chosen_year].free_cash_flow < financials[chosen_year].net_income or \
                        financials[chosen_year].free_cash_flow < financials[chosen_year].net_income:
            return False

        pe = self.info_dict[symbol]["Price"] / financials["TTM"].eps
        lastYear = str(int(chosen_year)-1)
        latestYoYRevenueGrowth = financials[chosen_year].revenue/financials[lastYear].revenue - 1
        latestYoYEPSGrowth = financials[chosen_year].eps/financials[lastYear].eps - 1
        latestYoYNetIncomeGrowth = financials[chosen_year].net_income/financials[lastYear].net_income - 1

        # company pe needs to be reasonble <=50
        # company is growing
        if pe > 50 or latestYoYEPSGrowth <0 or latestYoYNetIncomeGrowth <0 or latestYoYRevenueGrowth < 0.05:
            return False

        # for high PE stock, PEG need to be small, which means the growth is fast
        if pe>20:
            peg = pe / latestYoYNetIncomeGrowth / 100.0
            if peg > 1.15:
                return False
            else:
                self.high_growth_list.append(stock)
        return True

if __name__ == '__main__':
    sp500 = getSP500List()

    stock_info_fetcher = StocksStatsFetcher(stock_list=sp500[1:100],data_requester=FinancialDataRequester())
    stock_info_fetcher.check_stock_financials()

    print("##### Qualified Stock List #####\n")
    print("\n".join(stock_info_fetcher.qualified_stocks()))
    print("\n\n##### Qualified High Growth Stock List #####\n")
    print("\n".join(stock_info_fetcher.high_growth_stocks()))
