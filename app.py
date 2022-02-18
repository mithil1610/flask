import os
from flask import Flask, Response, jsonify, render_template, logging, request, make_response
from flask_cors import CORS, cross_origin
import json
from github3 import login
import dateutil.relativedelta
from dateutil import *
from datetime import date, timedelta
import pandas as pd
import time

app = Flask(__name__)
CORS(app)


def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add('Access-Control-Allow-Headers', "*")
    response.headers.add('Access-Control-Allow-Methods', "*")
    return response


def _corsify_actual_response(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


def forecast(issues_reponse, type="created_at"):
    data_frame = pd.DataFrame(issues_reponse)
    df1 = data_frame.groupby([type], as_index=False).count()
    df = df1[[type, 'issue_number']]
    df.columns = ['ds', 'y']

    df['ds'] = df['ds'].astype('datetime64[ns]')
    array = df.to_numpy()
    x = np.array([time.mktime(i[0].timetuple()) for i in array])
    y = np.array([i[1] for i in array])

    lzip = lambda *x: list(zip(*x))

    days = df.groupby('ds')['ds'].value_counts()
    Y = df['y'].values
    X = lzip(*days.index.values)[0]
    firstDay = min(X)

    # To achieve data consistancy with both actual data and predicted values, I'm adding zeros to dates that do not have orders
    # [firstDay + timedelta(days=day) for day in range((max(X) - firstDay).days + 1)]
    Ys = [0, ]*((max(X) - firstDay).days + 1)
    days = pd.Series([firstDay + timedelta(days=i) for i in range(len(Ys))])
    for x, y in zip(X, Y):
        Ys[(x - firstDay).days] = y

    # modify the data that is suitable for LSTM
    Ys = np.array(Ys)
    Ys = Ys.astype('float32')
    Ys = np.reshape(Ys, (-1, 1))
    scaler = MinMaxScaler(feature_range=(0, 1))
    Ys = scaler.fit_transform(Ys)
    train_size = int(len(Ys) * 0.80)
    test_size = len(Ys) - train_size
    train, test = Ys[0:train_size, :], Ys[train_size:len(Ys), :]
    print('train size:', len(train), ", test size:", len(test))

    def create_dataset(dataset, look_back=1):
        X, Y = [], []
        for i in range(len(dataset)-look_back-1):
            a = dataset[i:(i+look_back), 0]
            X.append(a)
            Y.append(dataset[i + look_back, 0])
        return np.array(X), np.array(Y)

    # Look back decides how many days of data the model looks at for prediction
    look_back = 1  # Here LSTM looks at approximately one month data
    X_train, Y_train = create_dataset(train, look_back)
    X_test, Y_test = create_dataset(test, look_back)

    # reshape input to be [samples, time steps, features]
    X_train = np.reshape(X_train, (X_train.shape[0], 1, X_train.shape[1]))
    X_test = np.reshape(X_test, (X_test.shape[0], 1, X_test.shape[1]))

    # verifying the shapes
    X_train.shape, X_test.shape, Y_train.shape, Y_test.shape

    # # Model to forecast orders for all zip code
    model = Sequential()
    model.add(LSTM(100, input_shape=(X_train.shape[1], X_train.shape[2])))
    model.add(Dropout(0.2))
    model.add(Dense(1))
    model.compile(loss='mean_squared_error', optimizer='adam')

    history = model.fit(X_train, Y_train, epochs=20, batch_size=70, validation_data=(X_test, Y_test),
                        callbacks=[EarlyStopping(monitor='val_loss', patience=10)], verbose=1, shuffle=False)

    # model.summary()

    plt.figure(figsize=(8, 4))
    plt.plot(history.history['loss'], label='Train Loss')
    plt.plot(history.history['val_loss'], label='Test Loss')
    plt.title('model loss for ' + type)
    plt.ylabel('loss')
    plt.xlabel('epochs')
    plt.legend(loc='upper right')
    plt.savefig("static/images/model_loss_" + type + ".png")

    # predict issues for test data
    y_pred = model.predict(X_test)

    fig, axs = plt.subplots(1, 1, figsize=(20, 8))
    X = mdates.date2num(days)
    axs.plot(np.arange(0, len(Y_train)), Y_train, 'g', label="history")
    axs.plot(np.arange(len(Y_train), len(Y_train) + len(Y_test)),
             Y_test, marker='.', label="true")
    axs.plot(np.arange(len(Y_train), len(Y_train) + len(Y_test)),
             y_pred, 'r', label="prediction")
    axs.legend()
    axs.set_title('LSTM generated data for ' + type)
    axs.set_xlabel('Time steps')
    axs.set_ylabel('Issues')
    plt.savefig("static/images/lstm_generated_data_" + type + ".png")

    fig, axs = plt.subplots(1, 1, figsize=(20, 8))
    X = mdates.date2num(days)
    axs.plot(X, Ys, 'purple', marker='.')
    locator = mdates.AutoDateLocator()
    axs.xaxis.set_major_locator(locator)
    axs.xaxis.set_major_formatter(mdates.AutoDateFormatter(locator))
    axs.legend()
    axs.set_title('All Issues data')
    axs.set_xlabel('Date')
    axs.set_ylabel('Issues')
    plt.savefig("static/images/all_issues_data_" + type + ".png")


@app.route('/github', methods=['GET', 'POST'])
@cross_origin()
def github():
    repo_name = "angular/angular"
    # body = request.get_json()
    # repo_name = body['repository']
    token = os.environ.get(
        'GITHUB_TOKEN', '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')
    github = login(token=token)

    today = date.today()

    response = {
        "issues": None,
        "stars": None,
        "forkCount": None
    }
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

    response['issues'] = issues_reponse
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
    response['stars'] = repository.stargazers_count
    response['forkCount'] = repository.forks_count

    # Forecasting
    # forecast(issues_reponse, type="created_at")
    # forecast(issues_reponse, type="closed_at")

    json_response = {
        "created": created_at_issues,
        "closed": closed_at_issues,
        "starCount": repository.stargazers_count,
        "forkCount": repository.forks_count
    }
    return jsonify(json_response)


# run server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
