#!/usr/bin/python3

import json, glob, platform, os, argparse, datetime
import regex as re
import pandas as pd
import numpy as np
import pickle as pkl
from bs4 import BeautifulSoup
from cad_lib import isnotebook, ROOT_DIR, EMPTY_LIMIT

CNTY_SFFX = 'tomgreen'

if isnotebook():
    from tqdm.notebook import tqdm, trange
else:
    from tqdm import tqdm, trange

def clean_substrings(input_array):
    bad_substrings = ['$', '&nbsp;', 'Situs: ', 'Legal: ', '<strong>', '</strong>']
    element = ' '.join([str(entry) for entry in input_array])
    for sub in bad_substrings:
        element = element.replace(sub, '')
    element = element.replace('&amp;', '&').replace('   ', ' ').replace('  ', ' ').replace(' <br/>', ',')
    return element


def entries_to_line(soup, fields):
    soup_elements = [soup.find(id=field) for field in fields]
    table_cells   = [clean_substrings(element.contents) for element in soup_elements]
    line          = ', '.join([cell for cell in table_cells if cell!=" "])
    return line

if __name__ == '__main__':

    data_dir   = f'{ROOT_DIR}/data/data_{CNTY_SFFX}'
    output_dir = f'{ROOT_DIR}/output/output_{CNTY_SFFX}'
    os.makedirs(output_dir, exist_ok=True)

    total_list = []

    for fname in tqdm(sorted(glob.glob(f'{data_dir}/prop_*.html'))):
        with open(fname, 'r') as f:
            html_text = f.read()

        soup              = BeautifulSoup(html_text, 'lxml')
        try:
            prop_id       = int(soup.find(id="ucidentification_webprop_id").contents[0][1:])
        except AttributeError:
            continue

        legal_description = entries_to_line(soup, ["webprop_desc"])
        prop_address      = entries_to_line(soup, ["webprop_situs"])
        owner_name        = entries_to_line(soup, ["webprop_name"])
        owner_address     = entries_to_line(soup, ["webprop_mailaddress"])
        sale_table        = soup.find(id='tableSale').contents
        transfer_date     = sale_table[0].contents[3].contents[0] if sale_table else ''

        if transfer_date and transfer_date.lower()!='n/a':
            transfer_date = datetime.datetime.strptime(transfer_date, "%m/%d/%Y").strftime('%Y-%m-%d')

        absentee          = 'Homestead' not in entries_to_line(soup, ["webprop_exemption"])
        imp_val           = float(entries_to_line(soup, ["histimp0_yr"]).replace(',',''))
        empty_land        = imp_val < EMPTY_LIMIT
        land_table        = soup.find(id="tableLnd").contents
        land_area         = float(land_table[0].contents[1].contents[0].replace(',','') if land_table else 0.0
        property_use      = land_table[0].contents[0].contents[0] if (land_table and land_table[0].contents[0].contents) else ''
        potential_schools = re.findall('>[^<]* ISD[^<]*<', html_text)
        school            = potential_schools[-1][1:-1] if potential_schools else ''

        try:
            with open(fname.replace('prop', 'tax'), 'r') as f:
                html_text = f.read()
        except FileNotFoundError:
            continue

        if 'tableBills' not in html_text:
            continue

        soup               = BeautifulSoup(html_text, 'lxml')
        tax_table          = soup.find(id="tableBills").contents[0].contents
        add_fees           = float(clean_substrings([str(tax_table[5].contents[0])]).replace(',', ''))
        late_fees          = float(clean_substrings([str(tax_table[6].contents[0])]).replace(',', ''))
        recent_penalty     = add_fees + late_fees
        recent_delinquency = float(clean_substrings([str(tax_table[7].contents[0])]).replace(',', ''))

        prop_dict          = {
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
                                 'zoning'           : property_use,
                                 'land_area'        : land_area,
#                                     'land_dict'        : land_dict,
                                 'recent_penalty'   : recent_penalty,
                                 'recent_delinq'    : recent_delinquency,
                                 'school'           : school,
#                                     'inactive'         : inactive
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
