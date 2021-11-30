#!/usr/bin/python3

import json, glob, platform, os, argparse, datetime
import regex as re
import pandas as pd
import numpy as np
import pickle as pkl
from bs4 import BeautifulSoup
from cad_lib import isnotebook, ROOT_DIR, EMPTY_LIMIT

CNTY_SFFX = 'jones'

if isnotebook():
    from tqdm.notebook import tqdm, trange
else:
    from tqdm import tqdm, trange

def entries_to_line(soup, fields):
    soup_elements = [soup.find(id=field) for field in fields]
    table_cells   = [element['value'] for element in soup_elements if 'value' in element.attrs]
    line          = ', '.join([cell for cell in table_cells if cell!=" "])
    return line


if __name__ == '__main__':

    if isnotebook():
        parse_properties, parse_owners, merge_data = False, False, True
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

    output_fname_owners = f'{output_dir}/output_{CNTY_SFFX}_owners.json'
    output_fname_prop   = f'{output_dir}/output_{CNTY_SFFX}_prop.json'


    if parse_properties:
        total_list = []

        for fname in tqdm(sorted(glob.glob(f'{data_dir}/prop_*.html'))):
            with open(fname, 'r') as f:
                html_text = f.read()

            soup              = BeautifulSoup(html_text, 'lxml')
            prop_id           = int(soup.find(id="txtParcel")['value'])
            legal_description = entries_to_line(soup, [f"txtLegal{num}" for num in range(1, 5)])
            prop_address      = entries_to_line(soup, ["txtPropAddress", "txtPropCityState"])
            owner_name        = entries_to_line(soup, ["txtName"])
            owner_address     = entries_to_line(soup, ["txtCareof", "txtStreet", "txtStreetOverflow", "txtCityState"])
            transfer_date     = entries_to_line(soup, ["txtSaleDeedDate"])
            if transfer_date:
                transfer_date = datetime.datetime.strptime(transfer_date, "%m/%d/%Y").strftime('%Y-%m-%d')
            absentee          = 'H' not in entries_to_line(soup, ["txtHomestead"])
            imp_val           = float(soup.find(id="txtImprovement")['value'].replace(',',''))
            empty_land        = imp_val < EMPTY_LIMIT
            land_area         = float(soup.find(id="txtAcres")['value'].replace(',',''))
            potential_schools = re.findall('>[^<]* ISD[^<]*<', html_text)
            school            = potential_schools[-1][1:-1] if potential_schools else ''
            property_use      = soup.find(id="txtCatCode")['value']
            # ^---- decode it later, try the following sources after figuring out unique entries:
            # https://comptroller.texas.gov/taxes/property-tax/docs/96-313.pdf
            # https://www.taxnetusa.com/research/texas/sptb.php
            # https://comptroller.texas.gov/taxes/property-tax/reappraisals/denton15-16.pdf

            prop_dict         = {
                                     'prop_id'          : prop_id,
                                     'legal_description': legal_description,
                                     'prop_address'     : prop_address,
                                     'owner_name'       : owner_name,
                                     'owner_address'    : owner_address,
                                     'transfer_date'    : transfer_date,
                                     'absentee'         : absentee,
                                     'empty_land'       : empty_land,
                                     'improvement_value': int(imp_val),
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
            with open(output_fname_prop, 'w') as json_f:
                json_f.write(json.dumps(total_list))

    if parse_owners:
        total_list = []

        for fname in tqdm(sorted(glob.glob(f'{data_dir}/owner_*.html'))):
            with open(fname, 'r') as f:
                html_text = f.read()

            soup        = BeautifulSoup(html_text, 'lxml')
            owner_id    = int(soup.find(id="txtOwnerID")['value'])
            delinq_flag = 'delinquent taxes due' in html_text

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
            with open(output_fname_owners, 'w') as json_f:
                json_f.write(json.dumps(total_list))

    if merge_data:
        df1            = pd.read_json(output_fname_prop)
        df2            = pd.read_json(output_fname_owners)
        df             = df1.merge(df2, on='prop_id', how='left')
        missing_owners = np.unique(df[df.owner_id.isna()].owner_name.values)

        with open(f'{output_dir}/missing_owners.pkl', 'wb') as f:
            pkl.dump(missing_owners, f)

        df.drop_duplicates(inplace=True)
        df.drop(columns=['owner_id'], inplace=True)

        with open(f'{output_dir}/output_{CNTY_SFFX}.json', 'w') as json_f:
                        json_f.write(json.dumps(df.to_dict('records')))

        df.to_csv(f'{output_dir}/output_{CNTY_SFFX}.csv', index=False)

        node_name = platform.node()
        if re.match('ip\-\d+\-\d+\-\d+\-\d+\..*', node_name):
            aws_dir = '/var/www/html/output'
            os.makedirs(aws_dir, exist_ok=True)
            df.to_csv(f'{aws_dir}/output_{CNTY_SFFX}.csv', index=False)
