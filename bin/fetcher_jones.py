#!/usr/bin/python3

import os, time, requests, datetime, contextlib, argparse, sys
import regex as re
import pandas as pd
import numpy as np
from cad_lib import isnotebook, ROOT_DIR

HTTP_ATTEMPTS  = 1000
CNTY_SFFX      = 'jones'
OWNER_ID_SPLIT = 60000 #IDs above this are extracted from appraisal rolls
PROP_ID_SPLIT  = 60000 #IDs above this are extracted from appraisal rolls

if isnotebook():
    from tqdm.notebook import tqdm, trange
else:
    from tqdm import tqdm, trange

def generate_session_id(url='http://www.jonescad.org/search.aspx?clientid=jonescad'):
    request_res  = requests.get(url)
    assigned_url = request_res.url
    session_id   = assigned_url.split('/')[3]
    assert re.match('\(S\(.*\)\)', session_id), "Wrong format of the session ID"
    
    return session_id

def jones_import_ids(fname):
    df           = pd.read_excel(fname)
    owner_ids    = df['Owner ID # ']
    owner_ids    = owner_ids[owner_ids.notnull()]
    owner_ids    = owner_ids.values.astype(int)
    owner_ids    = np.unique(owner_ids)
    property_ids = df[' parcel #']
    property_ids = property_ids[property_ids.notnull()]
    property_ids = property_ids.astype(str).map(lambda x: x.split('/')[0]).values.astype(int)
    property_ids = np.unique(property_ids)
    
    return owner_ids, property_ids


if __name__ == '__main__':

    if isnotebook():
        fetch_properties, fetch_owners = False, False
    else:
        parser = argparse.ArgumentParser(description='What to fetch')
        parser.add_argument('--properties', help='fetch properties', dest='properties', action='store_true', required=False)
        parser.add_argument('--owners', help='fetch owners', dest='owners', action='store_true', required=False)
        parser.set_defaults(owners=False, properties=False)
        args   = parser.parse_args()
        fetch_properties, fetch_owners = args.properties, args.owners
    
    data_dir = f'{ROOT_DIR}/data/data_{CNTY_SFFX}'
    os.makedirs(data_dir, exist_ok=True)

    records_url   = 'http://www.jonescad.org/open_records.htm'
    response      = requests.get(records_url)
    href_lines    = re.findall(r'<a href="open records/[^>]*>', response.text)
    filenames     = [tag.strip(r'<a href="').strip(r'">"').split('"')[0] for tag in href_lines]
    tax_filenames = [fn for fn in filenames if re.match(".*real.*roll.*\.xls", fn.lower())]
    
    if not tax_filenames:
        sys.stderr.write('No appraisal file in county open records!')
        
    url_appraisal_roll = 'http://www.jonescad.org/'+tax_filenames[-1]
    url_appraisal_roll = url_appraisal_roll.replace('&amp;', '&')
    response           = requests.get(url_appraisal_roll)
    fname              = f'{data_dir}/appraisal_roll.xls'
    with open(fname, 'wb') as f:
                f.write(response.content)
            
    owner_ids, property_ids = jones_import_ids(fname)
    session_id              = generate_session_id()

    if fetch_owners: 
        begin_id, end_id = 1, OWNER_ID_SPLIT
        special_ids      = owner_ids[owner_ids>=OWNER_ID_SPLIT]
        all_owner_ids    = np.concatenate((np.arange(begin_id, end_id), special_ids))
        
        for owner_id in tqdm(all_owner_ids):
            url   = f'http://www.jonescad.org/{session_id}/ptaxowner.aspx?ID=Pay&Owner={owner_id}&prop=R'
            fname = f'{data_dir}/owner_{owner_id:06d}.html'

            for trial in range(HTTP_ATTEMPTS):
                response = requests.get(url)

                if 'Welcome to the P&amp;A Website!' not in response.text:
                    break

                if trial==HTTP_ATTEMPTS-1:
                    raise Exception(f'Connection timeout at owner_id={owner_id}')

                time.sleep(1)
                session_id = generate_session_id()

            if fr'value="{owner_id}"' not in response.text:
                with contextlib.suppress(FileNotFoundError): # delete file, if owner was removed from the county website
                    os.remove(fname)
            else:
                with open(fname, 'wb') as f:
                    f.write(response.content)
    
    if fetch_properties:
        begin_id, end_id = 10000, PROP_ID_SPLIT
        special_ids      = property_ids[property_ids>=PROP_ID_SPLIT]
        all_prop_ids     = np.concatenate((np.arange(begin_id, end_id), special_ids))
        
        for prop_id in tqdm(all_prop_ids):
            url   = f'http://www.jonescad.org/{session_id}/rgeneral.aspx?ID={prop_id}&seq=1'
            fname = f'{data_dir}/prop_{prop_id}.html'

            for trial in range(HTTP_ATTEMPTS):
                response = requests.get(url)

                if 'Welcome to the P&amp;A Website!' not in response.text:
                    break

                if trial==HTTP_ATTEMPTS-1:
                    raise Exception(f'Connection timeout at prop_id={prop_id}')

                time.sleep(1)
                session_id = generate_session_id()

            if fr'value="{prop_id}"' not in response.text:
                with contextlib.suppress(FileNotFoundError): # delete file, if property was removed from the county website
                    os.remove(fname)
            else:
                with open(fname, 'wb') as f:
                    f.write(response.content)
