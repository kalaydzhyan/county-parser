#!/usr/bin/python3

import json, glob, platform, os
import regex as re
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from cad_lib import isnotebook, ROOT_DIR, EMPTY_LIMIT

CNTY_SFFX = 'jones'

if isnotebook():
    from tqdm.notebook import tqdm, trange
else:
    from tqdm import tqdm, trange
    
def entries_to_line(soup, fields):
    soup_elements = [soup.find(id=field) for field in fields]
    line          = ', '.join([element['value'] for element in soup_elements if 'value' in element.attrs])
    return line

if __name__ == '__main__':

    if isnotebook():
        parse_properties, parse_owners, merge_data = True, False, False
    else:
        parser = argparse.ArgumentParser(description='What to generate')
        parser.add_argument('--properties', help='parse properties', dest='properties', action='store_true', required=False)
        parser.add_argument('--owners', help='parse owners', dest='owners', action='store_true', required=False)
        parser.add_argument('--merge', help='merge owners and properties', dest='merge', action='store_true', required=False)
        parser.set_defaults(owners=False, properties=False, merge=False)
        args   = parser.parse_args()
        parse_properties, parse_owners, merge_data = args.properties, args.owners, args.merge
    
    data_dir   = f'{ROOT_DIR}/data/data_{CNTY_SFFX}'
    output_dir = f'{ROOT_DIR}/output/output_{CNTY_SFFX}'
    os.makedirs(output_dir, exist_ok=True)

    if parse_properties:
        total_list = []
    
        for fname in tqdm(sorted(glob.glob(f'{data_dir}/prop_*.html'))): ## change later!
            with open(fname, 'rb') as f:
                html_text = f.read()
            
            soup              = BeautifulSoup(html_text, 'html.parser')
            prop_id           = int(soup.find(id="txtParcel")['value'])
            legal_description = entries_to_line(soup, [f"txtLegal{num}" for num in range(1, 5)])
            prop_address      = entries_to_line(soup, ["txtPropAddress", "txtPropCityState"])
            owner_name        = entries_to_line(soup, ["txtName"])
            owner_address     = entries_to_line(soup, ["txtCareof", "txtStreet", "txtStreetOverflow", "txtCityState"])
            absentee          = 'H' not in entries_to_line(soup, ["txtHomestead"])
            empty_land        = float(soup.find(id="txtImprovement")['value'].replace(',','')) < EMPTY_LIMIT
            land_area         = float(soup.find(id="txtAcres")['value'].replace(',',''))
            potential_schools = re.findall('>[^<]* ISD[^<]*<', html_text.decode('UTF8'))
            school            = potential_schools[-1][1:-1] if potential_schools else ''
            property_use      = soup.find(id="txtCatCode")['value']
            # ^---- decode it later, try the following sources after figuring out unique entries:
            # https://www.taxnetusa.com/research/texas/sptb.php
            # file:///Users/tigrank/Downloads/denton15-16.pdf (page 24)
            
            prop_dict         = {
                                     'prop_id'          : prop_id,
                                     'legal_description': legal_description,
                                     'prop_address'     : prop_address,
                                     'owner_name'       : owner_name,
                                     'owner_address'    : owner_address,
                                     'absentee'         : absentee,
                                     'empty_land'       : empty_land,
                                     'property_use'     : property_use,
#                                     'zoning'           : zoning,
                                     'land_area'        : land_area,
#                                     'land_dict'        : land_dict,
#                                     'recent_penalty'   : recent_penalty,
#                                     'recent_delinq'    : recent_delinquency,
                                     'school'           : school,
#                                     'inactive'         : inactive
                                 }

            total_list.append(prop_dict)

        if total_list:
            with open(f'{output_dir}/output_{CNTY_SFFX}.json', 'w') as json_f:
                json_f.write(json.dumps(total_list))
    
    
    if parse_owners:
        total_list = []
    
        for fname in tqdm(sorted(glob.glob(f'{data_dir}/owner_*.html'))):
            with open(fname, 'rb') as f:
                html_text = f.read()
                
            soup        = BeautifulSoup(html_text, 'html.parser')
            owner_id    = int(soup.find(id="txtOwnerID")['value'])
            delinq_flag = b'delinquent taxes due' in html_text
            
            # parsing the tax table
            data       = []
            table_body = soup.find(id="DataGrid1")
            rows       = table_body.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                cols = [ele.text.strip() for ele in cols]
                data.append([ele for ele in cols if ele])
                
            # fixing up html->table parsing problems
            data           = [[el for el in row if el not in ['Homestead', 'Receipt']] for row in data]
            df             = pd.DataFrame(data)
            df.columns     = df.iloc[0]
            df             = df[1:]
            df['owner_id'] = owner_id
            df             = df.rename(columns={'Parcel ID': 'prop_id', 
                                                'TotalPenalty & InterestAnd/Or Discount':'recent_penalty', 
                                                'Tax Due':'recent_delinq'})
            df             = df[['owner_id', 'prop_id', 'recent_penalty', 'recent_delinq']]
            df.prop_id     = df.prop_id.astype(int)
            
            for col in ['recent_penalty', 'recent_delinq']:
                df[col] = df[col].map(lambda x: x.replace(',','')).astype(float)

            if not delinq_flag:
                df.recent_delinq = 0.0

            total_list.extend(df.to_dict('records'))
            
        if total_list:
            with open(f'{output_dir}/output_{CNTY_SFFX}_owners.json', 'w') as json_f:
                json_f.write(json.dumps(total_list))
    
    
    if merge_data:
        pass
#         df = pd.DataFrame(total_list)
#         df.to_csv(f'{output_dir}/output_{CNTY_SFFX}.csv', index=False)

#         node_name = platform.node()
#         if re.match('ip\-\d+\-\d+\-\d+\-\d+\..*', node_name):
#             aws_dir = '/var/www/html/output'
#             os.makedirs(aws_dir, exist_ok=True) 
#             df.to_csv(f'{aws_dir}/output_{CNTY_SFFX}.csv', index=False)
