#!/usr/bin/python3

import os, time, requests, datetime, contextlib, argparse, sys, glob
import regex as re
import pandas as pd
import numpy as np
import pickle as pkl
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from cad_lib import isnotebook, ROOT_DIR, FileLock, Timeout

HTTP_ATTEMPTS  = 200
HTTP_TIMEOUT   = 10*60 #There are 5min+ delays observed with the county website
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

def owner_name_to_ids(owner_name, driver=None):
    if driver is None:
        options = Options()
        options.headless = True
        driver = webdriver.Chrome(options=options)

    session_id = generate_session_id()
    driver.get(f'http://jonescad.org/{session_id}/search.aspx?clientid=jonescad')
    driver.find_elements_by_xpath("//input[@name='radSearch' and @value='radPropTax']")[0].click()
    driver.find_elements_by_xpath("//input[@name='radPanelChoice' and @value='radOwnerName']")[0].click()
    driver.find_element_by_id('txtUserInput').send_keys(owner_name)
    driver.find_elements_by_xpath('//*[@id="btnSearch"]')[0].click()
    
    if 'no results' in driver.page_source:
        owner_ids = []
    else:
        owner_instances = re.findall('Owner=\d*', driver.page_source) 
        owner_ids = [int(line.split('=')[1]) for line in owner_instances]
        
    return owner_ids

def extract_missing_owners(fname):
    if os.path.exists(fname):
        with open(fname, 'rb') as f:
            owner_names = pkl.load(f)
            
## Not stable with Jones county website
#         options          = Options()
#         options.headless = True
#         driver           = webdriver.Chrome(options=options)

        extra_ids = []

        for owner_name in owner_names:
            ids = owner_name_to_ids(owner_name)
            extra_ids.extend(ids)
        
        result_ids = np.unique(extra_ids)
    else:
        result_ids = []
        
    return result_ids


if __name__ == '__main__':

    if isnotebook():
        fetch_properties, fetch_owners = False, True
    else:
        parser = argparse.ArgumentParser(description='What to fetch')
        parser.add_argument('--properties', help='fetch properties', dest='properties', action='store_true', required=False)
        parser.add_argument('--owners', help='fetch owners', dest='owners', action='store_true', required=False)
        parser.set_defaults(owners=False, properties=False)
        args   = parser.parse_args()
        fetch_properties, fetch_owners = args.properties, args.owners
    
    data_dir   = f'{ROOT_DIR}/data/data_{CNTY_SFFX}'
    output_dir = f'{ROOT_DIR}/output/output_{CNTY_SFFX}'
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

    with FileLock(fname) as f_lock: # preventing simultaneous dumping
        with open(fname, 'wb') as f:
            f.write(response.content)
            
    owner_ids, property_ids = jones_import_ids(fname)
    session_id              = generate_session_id()

    if fetch_owners: 
        begin_id, end_id = 1, OWNER_ID_SPLIT
        standard_ids     = np.arange(begin_id, end_id)
        existing_fnames  = glob.glob(f'{ROOT_DIR}/data/data_{CNTY_SFFX}/owner*')
        existing_ids     = [int(fname.split('/')[-1].replace('owner_', '').replace('.html', '')) for fname in existing_fnames]
        special_ids      = owner_ids[owner_ids>=OWNER_ID_SPLIT]
        missing_ids      = extract_missing_owners(f'{output_dir}/missing_owners.pkl')
        all_owner_ids    = np.concatenate((standard_ids, existing_ids, special_ids, missing_ids))
        all_owner_ids    = np.unique(all_owner_ids)
        
        for owner_id in tqdm(all_owner_ids):
            fname = f'{data_dir}/owner_{owner_id:08d}.html'

            for trial in range(HTTP_ATTEMPTS):
                with Timeout(HTTP_TIMEOUT):
                    url      = f'http://www.jonescad.org/{session_id}/ptaxowner.aspx?ID=Pay&Owner={owner_id}&prop=R'
                    response = requests.get(url)
                    
                    if response.ok and 'Welcome to the P&amp;A Website!' not in response.text:
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
            fname = f'{data_dir}/prop_{prop_id:06d}.html'

            for trial in range(HTTP_ATTEMPTS):
                with Timeout(HTTP_TIMEOUT):
                    url      = f'http://www.jonescad.org/{session_id}/rgeneral.aspx?ID={prop_id}&seq=1'
                    response = requests.get(url)

                    if response.ok and 'Welcome to the P&amp;A Website!' not in response.text:
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
