#!/usr/bin/python3

import zipfile, requests, os, tempfile
import pandas as pd
import datetime as dt
import regex as re
from cad_lib import ROOT_DIR

if __name__ == '__main__':
    
    today       = dt.datetime.today()
    months_list = pd.date_range(today - dt.timedelta(days=600), today, freq='MS').strftime("%Y/%m").tolist()
    url_root    = 'https://www.callahancad.org/wp-content/uploads/'

    for month in reversed(months_list):
        url           = f'{url_root}{month}/'
        response      = requests.get(url)
        href_lines    = re.findall("<a href=[^>]*>", response.text)
        filenames     = [tag.strip(r'<a href="').strip(r'">"') for tag in href_lines]
        tax_filenames = [fn for fn in filenames if re.match(".*tax.*\.zip", fn.lower())]

        if tax_filenames:
            url_tax = url+tax_filenames[-1]
            break

    data_folder = f'{ROOT_DIR}/data/data_callahan'
    os.makedirs(data_folder, exist_ok=True)
    
    for f in os.listdir(data_folder):
        os.remove(f'{data_folder}/{f}')
    
    with tempfile.TemporaryFile() as tfile:
        response = requests.get(url_tax)
        tfile.write(response.content)
        with zipfile.ZipFile(tfile, "r") as zipf:
            zipf.extractall(data_folder)
