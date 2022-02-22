
Step1: What will Flask do?
       1. Flask will take the repository_name from the body of the api(i.e. from React) and will fetch the created and closed issues 
          for the given repository for past 1 year
       2. Additionally, it will also fetch the author_name and other information for the created and closed issues.
       3. It will use group_by to group the created and closed issues for a given month and will return back the data to client
       4. It will then use the data obtained from the GitHub and pass it as a input request in the POST body to LSTM microservice
          to predict and to forecast the data
       5. The response obtained from LSTM microservice is also return back to client. 

Step2: Deploying React to gcloud platform
       1: You must have Docker(https://www.docker.com/get-started) and Google Cloud SDK(https://cloud.google.com/sdk/docs/install) 
           installed on your computer.Additionally you have to edit .yaml file that is provided to you with your 
           GCloud project id and GCloud project name

       2: Type `docker` on cmd terminal and press enter to get all required information

       3: Type `docker build .` on cmd to build a docker image

       4: Type `docker images` on cmd to see our first docker image. After hitting enter, newest created image will be always on the top of the list

       5: Now type `docker tag <your newest image id> gcr.io/<your project-id>/<project-name>` and hit enter 
            Type `docker images` to see your image id updated with tag name

       6: Type `gcloud init` on cmd

       7: Type `gcloud auth configure-docker` on cmd

       8: Go to your GCloud account and open container registry

       9: Enable your billing account

       10: Enable your Container Registry API

       11: Go to the Cloud Build and enable Cloud Build API

       12: Type `docker push <your newest created tag>` on cmd and hit enter

       13: You have make your empty github repository and generate GitHub Access token and have to push your code to repository.

       14: Go to cloud run and create new service, service name will be your GCloud project name and for container image url 
            hit select and selects your latest id and hit select and edit container port to '5000', increase the memory limit 
            to 1GiB and add GitHub Access token in Environment variable and hit create.

       15: This will create the service on port 5000 and will generate the url, hit the url.

Step3: To run locally:
       1. In app.py, at line 43, add your GitHub token
       2. Go to cmd terminal and type following:
        a. python -m venv env
        b. env\Scripts\activate.bat
        c. pip install -r requirements.txt
        d. python app.py