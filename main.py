'''
Copyright (c) 2021 Cisco and/or its affiliates.

This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at

               https://developer.cisco.com/docs/licenses

All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
'''

from flask import Flask, render_template, request, make_response
from env_var import config
import requests
import re
import pandas as pd

app = Flask(__name__)

# configuration
api_key = config['api_key']
organization_id = config['organization_id']

## networks = create a list of networks from the org id
def get_networks(api_key, organization_id):
    url = f"https://api.meraki.com/api/v0/organizations/{organization_id}/networks"

    payload = None

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Cisco-Meraki-API-Key": api_key
    }

    response = requests.request('GET', url, headers=headers, data = payload)

    networks = response.json()
    return networks

networks = get_networks(api_key, organization_id)
firewall_rules_with_ip = []
selected_network = {}
firewall_rules = []
policy_objects = []

def get_firewall_rules(api_key, organization_id, network_id):
    url = f"https://api.meraki.com/api/v0/organizations/{organization_id}/networks/{network_id}/l3FirewallRules"

    payload = None

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Cisco-Meraki-API-Key": api_key
    }

    response = requests.request('GET', url, headers=headers, data = payload)
    firewall_rules = response.json()
    return firewall_rules

def get_policy_objects(api_key, organization_id):
    url = f"https://api.meraki.com/api/v1/organizations/{organization_id}/policyObjects"

    payload = None

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Cisco-Meraki-API-Key": api_key
    }

    response = requests.request('GET', url, headers=headers, data = payload)
    policy_objects = response.json()
    return policy_objects


def get_firewall_rules_with_ip(firewall_rules, policy_objects):
    firewall_rules_with_IP = []
    for rule in firewall_rules:
        rule_updated = rule
        if not 'Any' in rule['srcCidr']:
            groups = re.findall("\d+", rule['srcCidr'])
            cidr_list = []
            for grp in groups:
                for policy_object in policy_objects:
                    if grp in policy_object['groupIds']:
                        cidr_list.append(policy_object['cidr'])
            rule_updated['srcCidr'] = cidr_list
            
        if not 'Any' in rule['destCidr']:
            cidr_list = []
            groups = re.findall("\d+", rule['destCidr'])
            for grp in groups:
                for policy_object in policy_objects:
                    if grp in policy_object['groupIds']:
                        cidr_list.append(policy_object['cidr'])
            rule_updated['destCidr'] = cidr_list
        firewall_rules_with_IP.append(rule_updated)
    return firewall_rules_with_IP

def get_csv_from_firewall_rules(firewall_rules_with_ip):
    df = pd.DataFrame(firewall_rules_with_ip)
    columns_to_drop = ['syslogEnabled']
    df = df.drop(columns_to_drop, axis = 1)
    columns_order = ['policy', 'comment', 'protocol', 'srcCidr', 'srcPort', 'destCidr', 'destPort']
    df = df[columns_order]
    df.columns = ['Policy', 'Rule Description', 'Protocol', 'Source IP', 'Source Port', 'Destination IP', 'Destination Port']
    csv = df.to_csv(index=False)
    return csv

@app.route("/")
def main_page():
    firewall_rules_with_ip = []

    return render_template("columnPage.html", firewall_rules=firewall_rules_with_ip, networks=networks, selected_network=selected_network)

@app.route("/selection", methods=['POST', 'GET'])
def selection_page():
    global selected_network
    global firewall_rules
    global firewall_rules_with_ip
    global policy_objects

    if request.method == 'POST':
        form_data = request.form
        print(form_data)
        network_id = form_data['network_id']

        # Determine whether network has been selected before or not
        try:
            network_selected_already = network_id == selected_network['id']
        except:
            network_selected_already = False

        # Gather network info from selected network
        if not network_selected_already:
            for network in networks:
                if network['id'] == network_id:
                    selected_network = network

        ##get list of firewall rules
        # Note: if network selected already, then firewall rules are in cache
        if not network_selected_already:
            firewall_rules = get_firewall_rules(api_key, organization_id, network_id)
            policy_objects = get_policy_objects(api_key, organization_id)
            firewall_rules_with_ip = get_firewall_rules_with_ip(firewall_rules, policy_objects)

        try:
            # User clicked button to download csv
            form_data['download_button']

            # convert json to csv
            csv = get_csv_from_firewall_rules(firewall_rules_with_ip)

            response = make_response(csv)

            filename = f"{selected_network['id']}_{selected_network['name']}_firewall_rules.csv"

            response.headers.set("Content-Disposition", "attachment", filename=filename)

            return response
        except:
            print("Did not click the csv download")

        return render_template("columnPage.html", firewall_rules=firewall_rules_with_ip, networks=networks, selected_network=selected_network)

    return render_template("columnPage.html", networks=networks, selected_network=selected_network)


if __name__ == "__main__":
    app.run(port="8000", host="127.0.0.1")
