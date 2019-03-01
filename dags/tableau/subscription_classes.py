import requests
import time
import os
import sys
import smtplib
import email
import imghdr
from datetime import date
from email.message import EmailMessage
from email.utils import make_msgid


def send_subscription(**kwargs):
    params = kwargs['params']
    tableau_config = params['tableau_config']
    subscription_config = params['subscription_config']
    tableau_group = params['tableau_group']
    workbook_name = params['workbook_name']
    workbook_view = params['workbook_view']
    env = params['env'] if 'env' in params.keys() else 'tableau_prod'
    template = params['template'] if 'template' in params.keys() else 'default'
    email_subject = params['email_subject'] if 'email_subject' in params.keys() else 'Tableau Dashboard Subscription'
    attachment_name = params['attachment_name'] if 'attachment_name' in params.keys() else 'dashboard'

    conn = TableauServer(tableau_config, env)
    subscription_email = SubscriptionEmail(subscription_config, conn, tableau_group,
        workbook_name, workbook_view, template, email_subject, attachment_name)

    conn.sign_in()
    subscription_email.build_distribution_list()
    refresh_job = conn.trigger_workbook_refresh(workbook_name)
    refresh_status = conn.wait_for_refresh(refresh_job)
    if refresh_status != 'Success':
        raise Exception('Failed to refresh the workbook {}'.format(workbook_name))
    subscription_email.build_pdf_report()
    subscription_email.build_png_image()
    subscription_email.send_email()
    conn.delete_temp_files()
    conn.sign_out()


class TableauServer:
    def __init__(self, config_json, env='tableau_prod'):
        """
        Initialize the TableauServer object.
        Variables set to 'None' will be populated during sign_in().
        The config_json parameter requires a valid config file.
        The env parameter is a string defaulting to 'tableau_prod'.
        """
        config = config_json
        tableau_env = env
        
        self.page_size = 1000  # Max page_size is 1000
        self.user_id = None
        self.site_id = None
        self.auth_token = None
        self.base_get_url = None
        self.default_headers = None
        self._user_details = None
    
        self.server = config[tableau_env]['server']
        self.api_version = config[tableau_env]['api_version']
        self.username = config[tableau_env]['username']
        self.password = config[tableau_env]['password']
        self.site_name = config[tableau_env]['site']
        self.cache_buster = config[tableau_env]['cache_buster']
        self.temp_dir = config[tableau_env]['temp_dir']


    class ApiCallError(Exception):
        """
        Default error to throw for invalid API responses
        """
        pass

    def _check_status(self, server_response, success_code):
        """
        Checks the server response for possible errors.
        server_response : response received from the server
        success_code : expected success code for the response
        Throws an ApiCallError exception if the API call fails.
        """
        if server_response.status_code != success_code:
            response_json = server_response.json()
            # Retrieve the error code, summary, and detail if the response contains them
            if 'error' in response_json.keys():
                error_attributes = response_json['error'].keys()
                error_summary = response_json['error']['summary'] if 'summary' in error_attributes else None
                error_detail = response_json['error']['detail'] if 'detail' in error_attributes else None
                error_code = response_json['error']['code'] if 'code' in error_attributes else None
                error_message = '{0}: {1} - {2}'.format(error_code, error_summary, error_detail)
            else:
                error_message = 'Unknown error in the API response'
            raise self.ApiCallError(error_message)
        return

    def _populate_user_details(self):
        """
        Populates user details for all users on the site.
        This is useful for identifying users who have email addresses already.
        *NOTE* Do not rely on this function to get all user emails.
        Some user emails are not populated for some reason, and must be derived.
        """
        url = "{0}/api/{1}/sites/{2}/users?fields=id,email,fullName,name".format(self.server, self.api_version,
                                                                                 self.site_id)
        response = requests.get(url, headers=self.default_headers)
        self._user_details = response.json()['users']['user']

    def sign_in(self):
        """
        Sign in to the Tableau server
        server : server address
        api_version : version of API
        username : username
        password : the password for the user.
        site     : the site on the server to sign in to.
        Sets the authentication token, site ID, and user ID
        """
        url = "{0}/api/{1}/auth/signin".format(self.server, self.api_version)

        # Build the request
        json_request = {
            "credentials": {
                "name": self.username,
                "password": self.password,
                "site": {
                    "contentUrl": self.site_name
                }
            }
        }

        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Send the request to server
        response = requests.post(url, json=json_request, headers=request_headers)
        self._check_status(response, 200)

        # Save the auth token, site ID, user ID, and base_get_url
        self.auth_token = response.json()['credentials']['token']
        self.site_id = response.json()['credentials']['site']['id']
        self.user_id = response.json()['credentials']['user']['id']
        self.base_get_url = "{0}/api/{1}/sites/{2}".format(self.server, self.api_version, self.site_id)
        self.default_headers = {
            "X-Tableau-Auth": self.auth_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self._populate_user_details()
        
    def sign_out(self):
        """
        Sign out from Tableau Server
        """
        url = "{0}/api/{1}/auth/signout".format(self.server, self.api_version)
        response = requests.post(url, headers=self.default_headers)
        self._check_status(response, 204)
        print("Connection successfully closed.")
        
    def get_groups(self):
        """
        Returns a list of groups from the Tableau Server site
        """
        url = "{0}/api/{1}/sites/{2}/groups".format(self.server, self.api_version, self.site_id)
        response = requests.get(url, headers=self.default_headers)
        return response.json()['groups']['group']

    def get_group_by_name(self, group_name):
        """
        Returns a group object for the specified group name
        """
        groups = self.get_groups()
        try:
            return [group for group in groups if group['name'] == group_name].pop()
        except IndexError:
            print("The group '{0}' provided could not be found.".format(group_name))
            raise ValueError("Please pass a valid Tableau Server group name.")

    def get_email_users(self):
        """
        Returns a list of user objects,
        but only if the users have email addresses
        Purpose: compare this list to the users within a group.
        If any users in the group don't have email addresses, those emails need to be set.
        """
        url = "{0}/api/{1}/sites/{2}/users?fields=id,email,fullName,name".format(self.server, self.api_version, self.site_id)
        response = requests.get(url, headers=self.default_headers)
        all_users = response.json()['users']['user']
        return [user for user in all_users if 'email' in user.keys()]

    def get_users_from_group(self, group_name):
        """
        Returns a list of user objects belonging to the specified group_id,
        but only if the users have email addresses
        Purpose: compare this list to the users within a group.
        If any users in the group don't have email addresses, those emails need to be set.
        """
        group_id = self.get_group_by_name(group_name)['id']
        url = "{0}/api/{1}/sites/{2}/groups/{3}/users".format(self.server, self.api_version, self.site_id, group_id)
        response = requests.get(url, headers=self.default_headers)
        group_users = response.json()['users']['user']
        return [user for user in group_users]

    def get_users_comparison_staging(self, group_name):
        """
        Returns a set of user_id values from 'group_name' which have an email assigned on Tableau Server;
        Returns a set of user_id values belonging to the specified group
        Purpose: call on this list in another function
        """
        email_users = self.get_email_users()
        email_user_ids = set([user['id'] for user in email_users])
        group_users = self.get_users_from_group(group_name)
        group_user_ids = set([user['id'] for user in group_users])
        return email_user_ids, group_user_ids

    def get_users_missing_email(self, group_name):
        """
        Returns a set of user_id values which do not have an email assigned on Tableau Server
        Purpose: call on this list in another function to build email addresses for these users
        """
        email_user_ids, group_user_ids = self.get_users_comparison_staging(group_name)
        return group_user_ids.difference(email_user_ids)

    def get_users_having_email(self, group_name):
        """
        Returns a set of user_id values which have an email assigned on Tableau Server
        Purpose: call on this list in another function
        """
        email_user_ids, group_user_ids = self.get_users_comparison_staging(group_name)
        return group_user_ids.intersection(email_user_ids)

    def get_user_details(self, user_id):
        """
        Returns user details (name, fullName, email) for a specified user_id
        Purpose: called by other functions to build user emails, parse names, etc.
        """
        user_test = [user for user in self._user_details if user['id'] == user_id]
        return user_test

    def generate_makeshift_email(self, user_id):
        """
        Returns an activision email address for a specified user_id, assumed to be of the form:
        firstName.lastName@activision.com
        Purpose: generate email addresses for users who do not have one registered
        """
        url = "{0}/api/{1}/sites/{2}/users/{3}".format(self.server, self.api_version,
                                                       self.site_id, user_id)
        response = requests.get(url, headers=self.default_headers)
        user_details = response.json()['user']
        full_name = user_details['fullName'].split()
        first_name = full_name[1]
        last_name = full_name[0][0:-1]
        return "{0}.{1}@activision.com".format(first_name, last_name)

    def get_distribution_list(self, group_name):
        """
        Get the distribution list of user emails for the specified group.
        The group must be a Tableau Server group.
        Returns a list of emails as strings.
        """
        user_emails = []
        users_without_email = self.get_users_missing_email(group_name)
        users_with_email = self.get_users_having_email(group_name)
        [user_emails.append(self.get_user_details(user_id).pop()['email']) for user_id in users_with_email]
        [user_emails.append(self.generate_makeshift_email(user_id)) for user_id in users_without_email]
        return user_emails
        
    def get_subscription_workbooks(self, subscription_tag='subscription'):
        """
        Get all workbooks on the site which contain the tag 'subscription'
        Tags can be added manually via Tableau Server, or through API calls
        """
        url = "{0}/workbooks?filter=tags:eq:{1}".format(self.base_get_url, subscription_tag)
        response = requests.get(url, headers=self.default_headers)
        workbook_details = response.json()['workbooks']['workbook']
        return workbook_details
    
    def get_workbook_by_name(self, workbook_name):
        """
        Gets the workbook object details for the specified workbook name
        """
        workbook_details = self.get_subscription_workbooks()
        selected_workbook = [workbook for workbook in workbook_details if workbook['name'] == workbook_name]
        if len(selected_workbook) > 0:
            return selected_workbook
        else:
            raise ValueError('No workbook with the name provided was found. Try adding the tag "subscription" to the workbook on Tableau Server.')
    
    def get_workbook_id(self, workbook_name):
        """
        Gets the workbook ID for the specified workbook name
        This ID will be useful in other API calls
        """
        workbook = self.get_workbook_by_name(workbook_name).pop()
        return(workbook['id'])
    
    def trigger_workbook_refresh(self, workbook_name):
        """
        Triggers an extract refresh for the extracts of a specified workbook name.
        This function finds the datasource ID for the workbook,
        and then initiates the refresh for that datasource,
        returning a JSON object with details about the refresh job
        """
        workbook_id = self.get_workbook_id(workbook_name)
        url = "{0}/workbooks/{1}/refresh".format(self.base_get_url, workbook_id)
        response = requests.post(url, json={}, headers=self.default_headers)
        print(response.json())
        self._check_status(response, 202)
        job_details = response.json()
        print('job details: {}'.format(job_details))
        return job_details
    
    def trigger_datasource_refresh(self, workbook_name):
        """
        Triggers an extract refresh for the datasources of specified workbook name.
        This function finds the datasource ID for the workbook,
        and then initiates the refresh for that datasource,
        returning a JSON object with details about the refresh job
        """
        datasource_id = self.get_workbook_datasource_id(workbook_name)
        print('Refreshing datasource id: {}'.format(datasource_id))
        url = "{0}/datasources/{1}/refresh".format(self.base_get_url, datasource_id)
        response = requests.post(url, json={}, headers=self.default_headers)
        print(response.json())
        self._check_status(response, 202)
        job_details = response.json()
        print('job details: {}'.format(job_details))
        return job_details
    
    def wait_for_refresh(self, job_details):
        """
        Waits for the job ID of the specified job details to complete.
        Breaks out of the loop if the job details object has no ID.
        Waits until the job details object has the appropriate finish code.
        """
        time_in_seconds = 0
        time_interval = 30
        print("waiting for job: {}".format(job_details['job']['id']))
        while True:
            try:
                job_details = self.get_job_update(job_details['job']['id'])
            except:
                print('Error waiting for refresh -- object did not have a job ID.')
                break
            try:
                job_keys = job_details['job'].keys()
                if 'finishCode' in job_keys:
                    if job_details['job']['finishCode'] == '0':
                        print('Extract refresh job complete')
                        return 'Success'
                    elif job_details['job']['finishCode'] == '1':
                        print('Extract refresh job failed')
                        return 'Failure'
                    else:
                        print('Extract refresh job canceled')
                        return 'Failure'
            except KeyError:
                print('Job object did not have "job" key. Breaking loop.')
                return 'Failure'
            print('{0} seconds have passed since the task began.'.format(time_in_seconds))
            time.sleep(time_interval)
            time_in_seconds += time_interval
                
    def get_workbook_datasource_id(self, workbook_name):
        """
        Gets the datasource ID for the specified workbook.
        This will be used to refresh the extract for the named workbook.
        Returns the datasource ID.
        """
        workbook_id = self.get_workbook_id(workbook_name)
        url = "{0}/workbooks/{1}/connections".format(self.base_get_url, workbook_id)
        response = requests.get(url, headers=self.default_headers)
        print(response.json())
        self._check_status(response, 200)
        print('get_workbook_datasource_id response: {}'.format(response.json()))
        datasources = response.json()['connections']['connection']
        datasource_ids = [datasource['datasource']['id'] for datasource in datasources]
        return datasource_ids.pop() if len(datasource_ids) > 0 else None
    
    def get_job_update(self, job_id):
        """
        Gets the job status details for the specified job ID.
        This is used to track the progress of background tasks,
        such as extract refreshes.
        Returns an object of job details.
        """
        url = "{0}/jobs/{1}".format(self.base_get_url, job_id)
        response = requests.get(url, headers=self.default_headers)
        return response.json()
    
    def get_jobs(self):
        """
        Gets all jobs active on the site, only grabbing jobs that are not complete.
        Returns a JSON object filled with job detail objects.
        """
        url = "{0}/jobs?filter=progress:lt:100".format(self.base_get_url)
        response = requests.get(url, headers=self.default_headers)
        return response.json()
    
    def get_refresh_jobs(self):
        url = "{0}/tasks/extractRefreshes".format(self.base_get_url)
        response = requests.get(url, headers=self.default_headers)
        return response.json()
    
    def get_workbook_view_id(self, workbook_name, view_name):
        """
        Gets the view ID for the specified workbook / view combination.
        Workbooks may have multiple views,
        which is why the view name must be specified.
        Returns the view ID for the named workbook.
        """
        workbook_id = self.get_workbook_id(workbook_name)
        url = "{0}/workbooks/{1}/views".format(self.base_get_url, workbook_id)
        response = requests.get(url, headers=self.default_headers)
        self._check_status(response, 200)
        view_objects = response.json()['views']['view']
        view_id = [view for view in view_objects if view['name'] == view_name]
        return view_id.pop()['id'] if len(view_id) > 0 else print('Could not find the specified workbook view.')
    
    def get_workbook_pdf(self, workbook_name, view_name):
        """
        Gets a PDF file for the specified workbook / view combination.
        Writes the PDF file to the 'temp' repository,
        with filename 'report.pdf'.
        """
        workbook_view_id = self.get_workbook_view_id(workbook_name, view_name)
        url = "{0}/views/{1}/pdf".format(self.base_get_url, workbook_view_id)
        response = requests.get(url, headers=self.default_headers)
        self._check_status(response, 200)
        working_dir = os.getcwd()
        with open(working_dir + self.temp_dir + 'report.pdf', 'wb') as f:
            f.write(response.content)
            
    def get_workbook_png(self, workbook_name, view_name):
        """
        Gets a .PNG file for the specified workbook / view combination.
        Writes the .PNG file to the 'temp' repository,
        with filename 'report.png'.
        'cachebuster' is used to query a new view image object, which means
        we get the most updated image possible rather than an old cached image.
        """
        cache_buster_val = date.today() - date(2019, 1, 1)
        workbook_view_id = self.get_workbook_view_id(workbook_name, view_name)
        url = "{0}/views/{1}/image?vf_{2}={3}".format(self.base_get_url, workbook_view_id,
                                                      self.cache_buster, cache_buster_val.days)
        response = requests.get(url, headers=self.default_headers)
        self._check_status(response, 200)
        working_dir = os.getcwd()
        with open(working_dir + self.temp_dir + 'report.png', 'wb') as f:
            f.write(response.content)
            
    def delete_temp_files(self):
        """
        Deletes temp files, defined as any files existing within the
        'temp' repository.
        """
        working_dir = os.getcwd()
        temp_files = os.listdir(working_dir + self.temp_dir)
        [os.remove(working_dir + self.temp_dir + file) for file in temp_files if ('png' in file or 'pdf' in file)]


class SubscriptionEmail:
    def __init__(self, config_json, tableau_conn, 
                 tableau_group, workbook_name, workbook_view,
                 template='default', email_subject='Tableau Subscription',
                 attachment_name='dashboard'):
        self.config = config_json[template]
        self.tableau_conn = tableau_conn
        self.email_subject = email_subject
        self.tableau_group = tableau_group
        self.workbook_name = workbook_name
        self.workbook_view = workbook_view
        self.attachment_name = attachment_name
        self.username = self.config['smtp']['username']
        self.password = self.config['smtp']['password']
        self.smtp_server = self.config['smtp']['server']
        self.html_path = self.config['assets']['html_file']
        self.temp_dir = self.tableau_conn.temp_dir
        self.email_body = None
        self.distribution_list = None
        
    def refresh_extracts(self):
        job_details = self.tableau_conn.trigger_workbook_refresh(self.workbook_name)
        refresh_attempt = self.tableau_conn.wait_for_refresh(job_details)
        if refresh_attempt != 'Success':
            raise Exception('The Tableau extract refresh was unsuccessful. No subscription will be sent.')
        else:
            print('The Tableau extract refresh succeeded.')
        
    def build_distribution_list(self):
        self.distribution_list = self.tableau_conn.get_distribution_list(self.tableau_group)
    
    def build_pdf_report(self):
        self.tableau_conn.get_workbook_pdf(self.workbook_name, self.workbook_view)
        
    def build_png_image(self):
        self.tableau_conn.get_workbook_png(self.workbook_name, self.workbook_view)
        
    def send_email(self):
        msg = EmailMessage()
        dashboard_cid = make_msgid()
        
        msg['Subject'] = self.email_subject
        msg['From'] = self.username
    
        with open(os.getcwd() + self.html_path, 'r') as fp:
            html_body = fp.read()
            html_body = html_body.replace('{}', dashboard_cid[1:-1])
        msg.add_alternative(html_body, subtype='html')

        with open(os.getcwd() + self.temp_dir + 'report.png', 'rb') as img:
            msg.get_payload()[0].add_related(img.read(), 'image', 'png',
                                             cid=dashboard_cid)
        
        with open(os.getcwd() + self.temp_dir + 'report.pdf', 'rb') as fp:
            pdf_data = fp.read()
        msg.add_attachment(pdf_data, maintype='application/pdf', 
                           subtype='pdf', 
                           filename=(self.attachment_name + '.pdf'))
                
        with smtplib.SMTP(self.smtp_server) as mailServer:
            mailServer.ehlo()
            mailServer.starttls()
            mailServer.login(self.username, self.password)
            mailServer.sendmail(self.username,
                                self.distribution_list,
                                msg.as_string())
