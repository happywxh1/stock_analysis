import requests
import json
from collections import namedtuple
from bs4 import BeautifulSoup

COUNT_YEARS = 4
fields = ["revenue", "eps", "free_cash_flow", "net_income", "gross_margin"]
YearlyFinancialData = namedtuple("YearlyFinancialData", fields)
YearlyFinancialData.__new__.func_defaults = (None,) * len(YearlyFinancialData._fields)

def _getYear(time):
    return time.split("-")[0]

class FinancialDataRequester:

    def requestStockData(self, stock):
        financials = self._requestFinancialData(stock)
        if financials is None:
            return None
        data = self._requestPriceAndCapital(stock)
        if data is None:
            return None
        data["Financials"] = financials
        return data

    def _requestPriceAndCapital(self, stock):
        profileRequestUrl = "https://financialmodelingprep.com/api/company/profile/{}?datatype=json".format(stock)
        try:
            data = requests.get(profileRequestUrl).json()
            profile = {}
            profile["Capital"] = data[stock]["MktCap"]
            profile["Price"] = float(data[stock]["Price"])
            return profile
        except Exception as e:
            print("Fail to fetch profile of company %s with exception %s" % (stock, str(e)))
            return None


    def _requestFinancialData(self, stock):
        REQUEST_BASE_URL = "http://financials.morningstar.com/"
        financialRequestUrl = REQUEST_BASE_URL + "/finan/financials/getFinancePart.html?&t={}&region=usa&culture=en-US&cur=&order=desc".format(stock)

        data = requests.get(financialRequestUrl).json()
        htmlContent = BeautifulSoup(data["componentData"],"html.parser")
        items = htmlContent.find_all("tr")

        info = {}
        for item in items[1:]:
            if len(item) < 3:
                continue
            if item.find('span'):
                item.find('span').decompose()
            texts = item.get_text(separator="/", strip=True).split("/")

            try:
                if "Revenue" in texts[0]:
                    info["revenue"] = [float(n.replace(',','')) for n in texts[1:COUNT_YEARS+1]]
                elif "Gross Margin" in texts[0]:
                    info["gross_margin"] = []
                    for n in texts[1:COUNT_YEARS + 1]:
                        if len(n) > 2:
                            info["gross_margin"].append(float(n.replace(',',''))/100)
                        else:
                            info["gross_margin"].append(1.0)
                elif "Net Income" in texts[0]:
                    info["net_income"] = [float(n.replace(',','')) for n in texts[1:COUNT_YEARS+1]]
                elif "Earnings Per Share" in texts[0]:
                    info["eps"] = [float(n.replace(',','')) for n in texts[1:COUNT_YEARS+1]]
                #elif "Dividends" in texts[0]:
                #    info["dividends"] = [float(n.replace(',','')) for n in texts[1:COUNT_YEARS+1]]
                elif "Free Cash Flow" in texts[0] and "Per Share" not in texts[0]:
                    info["free_cash_flow"] = [float(n.replace(',','')) for n in texts[1:COUNT_YEARS+1]]
            except:
                print("Fail to get information for '%s' with text %s" % (stock, texts))
                return None

        time = items[0].get_text(separator="/", strip=True).split("/")[0:COUNT_YEARS]
        return self._organizeDataByYear(time, info)

    def _organizeDataByYear(self, time, data):
        financial = {}
        years = [_getYear(t) for t in time]
        for t in years:
            financial[t] = {}
        for k, v in data.items():
            idx = 0
            for d in v:
                financial[years[idx]][k]=d
                idx += 1
        for t in years:
            financial[t] = YearlyFinancialData(**financial[t])
        return financial
