import os
import json
import time
from functools import cache

import requests
import numpy as np
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from flask import Flask, render_template


app = Flask(__name__)


df = pd.read_csv('/Users/krishlakhani/PycharmProjects/RealEstateScoutingTool/Zillow properties listing information.csv')

@app.route('/')
def index():
    global df
    if os.path.exists('templates/property_map.html'):
        return render_template('property_map.html')
    else:
        df = df.dropna(subset=['longitude', 'latitude'])

        df['rentZestimate'] = pd.to_numeric(df['rentZestimate'], errors='coerce')
        df['zestimate'] = pd.to_numeric(df['zestimate'], errors='coerce')
        df['price'] = pd.to_numeric(df['price'], errors='coerce')

        df['annual_rent'] = df['rentZestimate'] * 12
        df['gross_rental_yield'] = (df['annual_rent']/df['zestimate']) * 100
        df['gross_rental_yield'] = df['gross_rental_yield'].replace([np.inf, -np.inf], np.ma)

        def get_marker_color(gross_yield, off_marker):
            if off_marker:
                return 'black'
            elif pd.isna(gross_yield):
                return 'gray'
            elif gross_yield < 5:
                return 'orange'
            else:
                return 'green'

        map_center = [df['latitude'].mean(), df['longitude'].mean()]
        m=folium.Map(location=map_center,zoom_start=12)
        marker_cluster=MarkerCluster().add_to(m)

        for idx,row in df.iterrows():
            price = row['price']
            address = row['address']
            bedrooms = row['bedrooms']
            bathrooms = row['bathrooms']
            living_area = row['livingArea']
            gross_yield = row['gross_rental_yield']
            zestimate = row['zestimate']
            rent_zestimate = row['rentZestimate']
            property_url = row['url']
            zpid = row['zpid']

            if not pd.isna(price):
                price_formatted=f'${price:.2f}'
            else:
                price_formatted='N/A'

            if not pd.isna(zestimate):
                zestimate_formattted=f'${zestimate:.2f}'
            else:
                zestimate_formattted='N/A'

            if not pd.isna(rent_zestimate):
                rent_zestimate_formattted=f'${rent_zestimate:.2f}'
            else:
                rent_zestimate_formattted='N/A'

            if not pd.isna(gross_yield):
                gross_yield_formattted=f'${gross_yield:.2f}'
            else:
                gross_yield_formattted='N/A'

            bedrooms=int(bedrooms) if not pd.isna(bedrooms) else 'N/A'
            bathrooms=int(bathrooms) if not pd.isna(bathrooms) else 'N/A'
            living_area=int(bedrooms) if not pd.isna(bedrooms) else 'N/A'

            address_dict=json.loads(address)
            street_address=address_dict['streetAddress']

            popup_text=f"""
            <b>Address:</b>{street_address}<br> 
            <b>Price:</b>{price_formatted}<br>
            <b>Bedrooms:</b>{bedrooms}<br>
            <b>Bathrooms:</b>{bathrooms}<br>
            <b>Living Area:</b>{living_area}<br>
            <b>Gross Rentals:</b>{gross_yield_formattted}<br>
            <b>Zestimane:</b>{zestimate_formattted}<br>
            <b>Rent Zestimate:</b>{rent_zestimate_formattted}<br>
            <a href="{property_url}" target="blank"> Zillow Link</a><br>
            <button id="button-{idx}" onclick="showLoadingAndRedirect({idx},'{zpid}')"> Show Pricing History</button>
            <div id="loading-{idx}" style="display:none;">
                <img src="https://images.app.goo.gl/oTou6XSeBTMYF5bMA" alt="Loading.." width="50" height="50">
            </div>
            
            <script>
                function showLoadingAndRedirect(idx,zpid){{
                    document.getElementById('button-'+idx).style.display='none';
                    document.getElementById('loading-'+idx).style.display='block'; 
                    window.location.href='http://localhost:5000/price_history/' + zpid;
                }}
            </script>                                                                                                  
            """
            color=get_marker_color(row['gross_rental_yield'],row['isOffMarket'])
            folium.Marker(
                location=[row['latitude'], row['longitude']],
                popup=folium.Popup(folium.IFrame(popup_text,width=300,height=250))    ,
                icon=folium.Icon(color=color,icon='home',prefix='fa')
            ).add_to(marker_cluster)
        m.save('templates/property_map.html')
        return render_template('property_map.html')

@app.route('/price_history/<int:zpid>')
@cache
def price_history(zpid):
    url=df[df.zpid==zpid].url.values[0]
    api_url="https://api.brightdata.com/datasets/v3/trigger?dataset_id=gd_lxu1cz9r88uiqsosl&include_errors=true"

    TOKEN=open('TOKEN','r').read()
    headers={
        "Authorisation":f"Bearer {TOKEN}",
        "Content-type":'application/json'
    }
    data=[{'url':url}]

    response=requests.post(api_url,headers=headers, json=data)
    snapshot_id=response.json()['snapshot_id']
    time.sleep(5)

    api_url=f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=json"

    headers={
        "Authorisation":f"Bearer {TOKEN}"
    }

    response=requests.get(api_url, headers=headers)

    if 'Snapshot is Empty' in response.text:
        return 'No historic data'
    while 'Snapshot is not ready yet, try again in 10 seconds' in response.text:
        time.sleep(10)
        response=requests.get(api_url, headers=headers)
        if 'Snapshot is Empty' in response.text:
            return 'No histotic data'

        with open('temp.csv','wb') as f:
            f.write(response.content)

        price_history_df=pd.read_csv('temp.csv')
        price_history_df=price_history_df[['date', 'price']]
        price_history_df['date']=pd.to_datetime(price_history_df['date'])
        price_history_df['date']=price_history_df.dt.strftime('%Y-%m-%d')

        return render_template(template_name_or_list='price_history.html',price_history_df=price_history_df)

if __name__== '__main__':
    app.run(debug=True)
        
