#!/usr/bin/python3

import os, glob, json, time, datetime, contextlib, platform
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import regex as re

from cad_lib import isnotebook, ROOT_DIR, EMPTY_LIMIT

CNTY_SFFX = 'taylor'

if isnotebook():
    from tqdm.notebook import tqdm, trange
else:
    from tqdm import tqdm, trange

    
if __name__ == '__main__':

    output_dir = f'{ROOT_DIR}/output/output_{CNTY_SFFX}'
    os.makedirs(output_dir, exist_ok=True) 

    total_list = []
    
    for fname in tqdm(sorted(glob.glob(f'{ROOT_DIR}/data/data_{CNTY_SFFX}/*.html'))):
    
        with open(fname, 'r') as f:
            html_text = f.read()

        # Skipping personal property, mobile homes, etc.
        if 'Type:</td><td>Real' not in html_text or 'No land segments' in html_text:
            continue
            
        inactive           = '(INACTIVE)' in html_text
        
        try:
            soup               = BeautifulSoup(html_text, 'lxml')
            tax_object         = soup.find(id="taxDueDetails_dataSection")
            table_entries      = tax_object.find_all('td')
            second_total_idx   = [index for index, s in enumerate(table_entries) if 'TOTAL' in s.text][1]
            recent_penalty     = float(table_entries[second_total_idx+5].text[1:])
        except:
            continue
        
        try:
            idx = next(table_entries.index(x) for x in table_entries if f'{datetime.datetime.now().year-1} TOTAL' in x.text)
            recent_delinquency = float(table_entries[idx+7].text[1:])
        except: # mostly ValueError and StopIteration
            recent_delinquency = 0.0
        
        try:
            school_line = next(x.text for x in table_entries if 'ISD' in x.text)
            school = school_line.split()[0]
            school = school.strip()
        except StopIteration:
            school = 'Unknown'
                    
        property_details  = soup.find(id="propertyDetails").find_all('td')
        prop_id           = int(property_details[2].text)
        legal_description = property_details[4].text
        property_use      = property_details[18].text
        prop_address      = property_details[23].text
        owner_name        = property_details[34].text
        owner_address     = ', '.join([s.strip() for s in property_details[38].strings])
        absentee          = 'HS' not in property_details[-1].text
        #empty_land        = 'No improvements exist for this property.' in html_text
        for element in soup.find(id="rollHistoryDetails").find_all('td')[1::7]:
            imp_val_text = element.text
            if imp_val_text!='N/A':   # property already appraised
                break
            
        improvement_value = int(imp_val_text.replace('$','').replace(',',''))
        empty_land        = improvement_value < EMPTY_LIMIT
        land_details      = soup.find(id="landDetails").find_all('td')
        land_textarray    = [s.text for s in land_details]
        stride            = 9
        land_types        = land_textarray[2::9]
        land_areas        = [float(s) for s in land_textarray[3::9]]
        land_area         = sum(land_areas)
        land_dict         = dict(zip(land_types, land_areas))
        zoning            = land_types[0] if len(land_types)==1 else 'Mixed' if land_types else 'Unknown'
        
        
        prop_dict         = {
                                'prop_id'          : prop_id,
                                'legal_description': legal_description,
                                'prop_address'     : prop_address,
                                'owner_name'       : owner_name,
                                'owner_address'    : owner_address,
                                'absentee'         : absentee,
                                'empty_land'       : empty_land,
                                'improvement_value': improvement_value,
                                'property_use'     : property_use,
                                'zoning'           : zoning,
                                'land_area'        : land_area,
                                'land_dict'        : land_dict,
                                'recent_penalty'   : recent_penalty,
                                'recent_delinq'    : recent_delinquency,
                                'school'           : school,
                                'inactive'         : inactive
                            }
        
        total_list.append(prop_dict)
        
    if total_list:
        with open(f'{output_dir}/output_{CNTY_SFFX}.json', 'w') as json_f:
            json_f.write(json.dumps(total_list))

        df = pd.DataFrame(total_list)
        df.to_csv(f'{output_dir}/output_{CNTY_SFFX}.csv', index=False)

        node_name = platform.node()
        if re.match('ip\-\d+\-\d+\-\d+\-\d+\..*', node_name):
            aws_dir = '/var/www/html/output'
            os.makedirs(aws_dir, exist_ok=True) 
            df.to_csv(f'{aws_dir}/output_{CNTY_SFFX}.csv', index=False)
        

        
