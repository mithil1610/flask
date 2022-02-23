import os
from flask import Flask, jsonify, request, make_response
from flask_cors import CORS, cross_origin
import json
from github3 import login
import dateutil.relativedelta
from dateutil import *
from datetime import date, timedelta
import pandas as pd
import time
import requests

app = Flask(__name__)
CORS(app)


def build_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "PUT, GET, POST, DELETE, OPTIONS")
    return response


def build_actual_response(response):
    response.headers.set("Access-Control-Allow-Origin", "*")
    response.headers.set("Access-Control-Allow-Methods", "PUT, GET, POST, DELETE, OPTIONS")
    return response


@app.route('/api/github', methods=['POST'])
def github():
    # repo_name = "angular/angular"
    body = request.get_json()
    repo_name = body['repository']
    # Add your own GitHub Token to run it local
    token = os.environ.get('GITHUB_TOKEN', 'Your GitHub Token')
    github = login(token=token)

    today = date.today()

    issues_reponse = []
    for i in range(12):
        last_month = today + dateutil.relativedelta.relativedelta(months=-1)
        types = 'type:issue'
        repo = 'repo:' + repo_name
        ranges = 'created:' + str(last_month) + '..' + str(today)
        search_query = types + ' ' + repo + ' ' + ranges

        for issue in github.search_issues(search_query):
            label_name = []
            data = {}
            current_issue = issue.as_json()
            current_issue = json.loads(current_issue)
            # Get issue number
            data['issue_number'] = current_issue["number"]
            # Get created date of issue
            data['created_at'] = current_issue["created_at"][0:10]
            if current_issue["closed_at"] == None:
                data['closed_at'] = current_issue["closed_at"]
            else:
                # Get closed date of issue
                data['closed_at'] = current_issue["closed_at"][0:10]
            for label in current_issue["labels"]:
                # Get label name of issue
                label_name.append(label["name"])
            data['labels'] = label_name
            # It gives state of issue like closed or open
            data['State'] = current_issue["state"]
            # Get Author of issue
            data['Author'] = current_issue["user"]["login"]
            issues_reponse.append(data)

        today = last_month

    df = pd.DataFrame(issues_reponse)

    # Daily Created At
    df_created_at = df.groupby(['created_at'], as_index=False).count()
    dataFrameCreated = df_created_at[['created_at', 'issue_number']]
    dataFrameCreated.columns = ['date', 'count']

    # Monthly Created At
    created_at = df['created_at'].sort_values(ascending=True)
    month_issue_created = pd.to_datetime(
        pd.Series(created_at), format='%Y/%m/%d')
    month_issue_created.index = month_issue_created.dt.to_period('m')
    month_issue_created = month_issue_created.groupby(level=0).size()
    month_issue_created = month_issue_created.reindex(pd.period_range(
        month_issue_created.index.min(), month_issue_created.index.max(), freq='m'), fill_value=0)
    month_issue_created_dict = month_issue_created.to_dict()
    created_at_issues = []
    for key in month_issue_created_dict.keys():
        array = [str(key), month_issue_created_dict[key]]
        created_at_issues.append(array)

    # Monthly Closed At
    closed_at = df['closed_at'].sort_values(ascending=True)
    month_issue_closed = pd.to_datetime(
        pd.Series(closed_at), format='%Y/%m/%d')
    month_issue_closed.index = month_issue_closed.dt.to_period('m')
    month_issue_closed = month_issue_closed.groupby(level=0).size()
    month_issue_closed = month_issue_closed.reindex(pd.period_range(
        month_issue_closed.index.min(), month_issue_closed.index.max(), freq='m'), fill_value=0)
    month_issue_closed_dict = month_issue_closed.to_dict()
    closed_at_issues = []
    for key in month_issue_closed_dict.keys():
        array = [str(key), month_issue_closed_dict[key]]
        closed_at_issues.append(array)

    org, name = repo_name.split("/")
    repository = github.repository(org, name)

    '''
        1. Hit LSTM Microservice by passing issues_response as body
        2. LSTM Microservice will give a list of string containing image paths hosted on google cloud storage
        3. On recieving a valid response from LSTM Microservice, append the above json_response with the response from
            LSTM microservice
    '''
    created_at_body = {
        "issues": issues_reponse,
        "type": "created_at"
    }
    closed_at_body = {
        "issues": issues_reponse,
        "type": "closed_at"
    }
    
    # Update your gcloud lstm url
    
    LSTM_API_URL = str("https://lstm-forecasting-y4hvjyxzra-uc.a.run.app") + str("/api/forecast")

    created_at_response = requests.post(LSTM_API_URL,
                                            json=created_at_body,
                                            headers={'content-type': 'application/json'})
    closed_at_response = requests.post(LSTM_API_URL,
                                            json=closed_at_body,
                                            headers={'content-type': 'application/json'})

    json_response = {
        "created": created_at_issues,
        "closed": closed_at_issues,
        "starCount": repository.stargazers_count,
        "forkCount": repository.forks_count,~
        "createdAtImageUrls": {
            **created_at_response.json(),
        },
        "closedAtImageUrls": {
            **closed_at_response.json(),
        },
    }

    return jsonify(json_response)


# run server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
