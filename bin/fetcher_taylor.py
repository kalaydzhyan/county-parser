#!/usr/bin/python3

import os, time, requests, datetime, contextlib, argparse
from cad_lib import isnotebook, ROOT_DIR

HTTP_ATTEMPTS = 1000

if isnotebook():
    from tqdm.notebook import tqdm, trange
else:
    from tqdm import tqdm, trange

def get_headers(url='https://propaccess.taylor-cad.org/clientdb/?cid=1'):
    session         = requests.Session()
    response        = session.get(url)
    session_cookies = session.cookies.get_dict()
    cookie_string   = '; '.join([f'{key}={session_cookies[key]}' for key in session_cookies])
    headers         = {
                          'cookie': cookie_string,
                          'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.114 Safari/537.36'
                      }
    return headers


if __name__ == '__main__':

    data_folder = f'{ROOT_DIR}/data/data_taylor'
    
    os.makedirs(data_folder, exist_ok=True) 
    headers = get_headers()

    if isnotebook():
        begin_id, end_id = 10000, 110000
    else:
        parser = argparse.ArgumentParser(description='Fetcher range')
        parser.add_argument('-begin_id', type=int, help='starting id', required=False, default=10000)
        parser.add_argument('-end_id', type=int, help='ending id', required=False, default=110000)
        args = parser.parse_args()
        begin_id, end_id = args.begin_id, args.end_id
    
    for prop_id in trange(begin_id, end_id):
        url   = f'https://propaccess.taylor-cad.org/ClientDB/Property.aspx?prop_id={prop_id}'
        fname = f'{data_folder}/{prop_id}.html'
        
        # Handling stale sessions
        for trial in range(HTTP_ATTEMPTS):
            response = requests.get(url, headers=headers)
            
            if response.ok:
                break
            
            if trial==HTTP_ATTEMPTS-1:
                raise Exception(f'Connection timeout at prop_id={prop_id}')
            
            time.sleep(1)
            headers  = get_headers()
            
        if 'Property not found.' in response.text:
            with contextlib.suppress(FileNotFoundError): # delete file, if property was removed from the county website
                os.remove(fname)
        else:
            with open(fname, 'wb') as f:
                f.write(response.content)
