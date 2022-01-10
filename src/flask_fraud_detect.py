from __future__ import unicode_literals
import os
import threading
import logging
import pandas as pd
import json
from flask import Flask, request
import joblib

from sklearn.linear_model._logistic import LogisticRegression
from sklearn.metrics._classification import (
    recall_score, confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.pipeline import Pipeline

#from settings import MODEL_FILENAME
PARENT_DIR_PATH = os.path.dirname(os.path.realpath(os.path.join(__file__, '..')))
MODEL_FILENAME = os.path.join(PARENT_DIR_PATH, "models", "model.pickle")
DATASET_FILENAME = os.path.join(PARENT_DIR_PATH, "data", "creditcard.csv")

app = Flask("Fraud Detection")

logger = logging.getLogger('training')

# load model at startup time
app.model = joblib.load(MODEL_FILENAME)

@app.route(u"/predict", methods=[u"POST"])
def predict_fraud():
    input_data = request.get_json()
    if u"features" not in input_data:
        return json.dumps({u"error": u"No features found in input"}), 400
    if not input_data[u"features"] or not isinstance(input_data[u"features"], list):
        return json.dumps({u"error": u"No feature values available"}), 400
    if isinstance(input_data[u"features"][0], list):
        results = app.model.predict_proba(input_data[u"features"]).tolist()
    else:
        results = app.model.predict_proba([input_data[u"features"]]).tolist()
    return json.dumps({u"scores": [result[1] for result in results]}), 200

@app.route(u"/training", methods=[u"POST"])
def training():
    data = request.get_json()
    thread = threading.Thread(target=start_training, kwargs={
                    'post_data': data})
    thread.start()
    return {"message": "Accepted"}, 202

def start_training(**kwargs):
    params = kwargs.get('post_data', {})
    """ Find the best model to fit the dataset and save it into file """
    # create a GridSearch object to find the best fitting model
    grid_search = new_grid_search()
    # run the search algorithm
    run_grid_search(grid_search)
    # save the best fitting model into FS
    save_search_results(grid_search)

def split_dataset():
    """ Read and split dataset into train and test subsets """
    df = pd.read_csv(DATASET_FILENAME, header=0)
    X = df[df.columns[:-1]].values
    y = df[df.columns[-1]].values
    return train_test_split(X, y, test_size=0.2, random_state=42)

def new_grid_search():
    """ Create new GridSearch obj with models pipeline """
    pipeline = Pipeline([
        # TODO some smart preproc can be added here
        (u"clf", LogisticRegression(class_weight="balanced")),
    ])
    search_params = {"clf__C": (1e-4, 1e-2, 1e0, 1e2, 1e4)}
    return GridSearchCV(
        estimator=pipeline,
        param_grid=search_params,
        scoring="recall_macro",
        cv=10,
        n_jobs=-1,
        verbose=3,
    )

def run_grid_search(grid_search, show_evaluation=True):
    """ Run the GridSearch algorithm and compute evaluation metrics """
    X_train, X_test, y_train, y_test = split_dataset()

    grid_search.fit(X_train, y_train)
    # for key, value in grid_search.cv_results_.items():
    #     print key, value

    predictions = grid_search.predict(X_test)

    if show_evaluation:
        logger.debug("macro_recall: %s", recall_score(y_test, predictions, average="macro"))
        logger.debug(precision_recall_fscore_support(y_test, predictions))
        logger.debug(confusion_matrix(y_test, predictions))

def save_search_results(grid_search):
    """ Serialize model into file """
    joblib.dump(grid_search.best_estimator_, MODEL_FILENAME)
    # then load it like this:
    # clf = joblib.load(model_dump_filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug = True)
