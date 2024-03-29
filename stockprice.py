import streamlit as st
import yfinance as yf
import pandas as pd
import base64

st.set_page_config(layout="wide")

# Sidebar + Main Panel
st.sidebar.header('Input Options')

# # Create the pandas DataFrame for stock tickername-code
tickerCode = [['Apple, AAPL','AAPL'],
['Google, GOOGL','GOOGL'],
['Microsoft, MSFT','MSFT'],
['Samsung Electronics, SSNLF','SSNLF'],
['Toyota Motor, TM','TM'],
['Honda Motor Company, HMC','HMC'],
['Nintendo, NTDOY','NTDOY'],
['Zoom Video Communications, ZM','ZM']]

df = pd.DataFrame(tickerCode, columns=['tickerName', 'tickerCode'])
values = df['tickerName'].tolist()
options = df['tickerCode'].tolist()
dic = dict(zip(options, values))
# Sidebar - define the ticker symbol
tickerSymbol = st.sidebar.selectbox('Select ticker', options, format_func=lambda x: dic[x])  
startDate = st.sidebar.date_input('Start date',value=pd.Timestamp('1990-01-01'))
endDate = st.sidebar.date_input('End date')

st.title('Simple Stock Price App')
st.write(f'Shown are the **stock closing price ** and **volume** of {tickerSymbol} !')

# get data on this ticker
tickerData = yf.Ticker(tickerSymbol)

# get the historical prices for this ticker
tickerDf = tickerData.history(period='1d',start=startDate,end=endDate)
tickerDf   # Open  High   Low  Close  Volume  Dividends   Stock Splits

st.write('## Closing Price')
st.line_chart(tickerDf.Close)
st.write('## Volume Price')
st.line_chart(tickerDf.Volume)

def download_link(object_to_download, download_filename, download_link_text):
    """
    Generates a link to download the given object_to_download.

    object_to_download (str, pd.DataFrame):  The object to be downloaded.
    download_filename (str): filename and extension of file. e.g. mydata.csv, some_txt_output.txt
    download_link_text (str): Text to display for download link.

    Examples:
    download_link(YOUR_DF, 'YOUR_DF.csv', 'Click here to download data!')
    download_link(YOUR_STRING, 'YOUR_STRING.txt', 'Click here to download your text!')

    """
    if isinstance(object_to_download,pd.DataFrame):
        object_to_download = object_to_download.to_csv(index=True)

    # some strings <-> bytes conversions necessary here
    b64 = base64.b64encode(object_to_download.encode()).decode()

    return f'<a href="data:file/txt;base64,{b64}" download="{download_filename}">{download_link_text}</a>'

if st.button('Download Dataframe as CSV'):
    tmp_download_link = download_link(tickerDf, 'output.csv', 'Click here to download your data!')
    st.markdown(tmp_download_link, unsafe_allow_html=True)