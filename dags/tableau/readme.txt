Welcome to the custom Tableau dashboard subscription email directory. 

Do not delete this directory or the files in this directory unless custom tableau subscriptions are deprecated. 

The 'temp' directory is used to store temporary .PNG and .PDF files for sending subscription emails.
The 'assets' directory is used to store HTML files for custom emails.
The 'config.py' file houses configuration settings for the TableauServer and EmailSubscription classes.

If this directory is deleted, custom subscription emails depending on this directory will fail.

Usage:

You will not need to directly use this directory. To make a custom email subscription, build a DAG file.
The DAG file should at some point have a task similar to the example provided below.

    call_exec_scorecard_daily = PythonOperator(
    	task_id='call_exec_scorecard_daily',
    	provide_context=True,
    	python_callable=send_subscription,
    	params={
    		'tableau_config': tableau_server_config,
    		'subscription_config': subscription_email_config,
    		'tableau_group': 'Executive Scorecards - Test',
    		'workbook_name': 'COD - Global - Snapshots & Scorecards - Executive Scorecard - Tesseract',
    		'workbook_view': 'COD Scorecard',
    		'email_subject': 'COD Executive Scorecard - Daily',
    		'attachment_name': 'COD Executive Scorecard - Daily'
    	}
    )

In the above example, all required parameters are assigned in the 'params' dict.

'tableau_config' identifies the dict from the 'config.py' file which will be used to configure the Tableau Server connection.
'subscription_config' identifies the dict from the 'config.py' file which will be used to configure the subscription email.
'tableau_group' identifies the Tableau Server group whose users will be emailed the subscription email.
	-> please make sure you have created an appropriate group on Tableau Server and have added the desired users to that group.
	-> please make sure your group also has the appropriate permissions to view the workbooks you are subscribing them to.
'workbook_name' identifies the Tableau Server workbook your subscription will use.
'workbook_view' identifies the view within the workbook that you would like to have emailed to your users in .PDF and .PNG form.
	-> the PDF file will be sent as an attachment with the email, while the PNG will be embedded in the email body.
'email_subject' specifies the subject line for the email that will be sent.
'attachment_name' specifies the name you would like assigned to your PDF file attachment.

(optional parameters, not used in the example above)
'template' names a specific email subscription configuration from the 'subscription_config' dict to be used.
	-> if you are including your own custom HTML file, you must add your new template to the 'config.py' file
	-> the default behavior is to use the 'default' template, which references the 'html_test.html' file as the email body.
	-> feel free to edit the 'html_test.html' file as needed to serve the team's purposes.

To build a new custom subscription email from scratch, you must:
1) Build the Tableau Workbook file.
2) Save the Tableau workbook file as a .twbx with an extract embedded in it before publishing.
	-> the REST API refresh methods in this workflow require that the workbook has an extract
	-> if desired, the team can work to develop methods for refreshing a datasource associted with the workbook
	-> caution: past attempts to refresh a datasource (rather than the workbook's embedded extract) did not work as intended
2) Publish the Tableau workbook file to Tableau Server to the appropriate project folder.
3) Create a tag for the Tableau Workbook when publishing (you can also edit the workbook details after publishing).
	-> one of the workbook tags MUST be set to 'subscription' (just the word, without the quotes)
4) Create or choose an existing Tableau Server group that contains the users you would like to send the subscription email to.
5) Note the name of the workbook you would like to use for the subscription.
	-> this must be an exact match
6) Note the name of the workbook view (sheet) you would like to use for the subscription.
	-> this must be an exact match
7) Create a new HTML file, or plan to use the existing default HTML file specified within the 'config.py' default template.
8) Create your DAG file, or add a new task to the existing 'cod_tableau_subscriptions.py' dag file in tesseract-python.
9) Set DAG dependencies appropriately.
10) Run airflow as you would normally and look for the subscription emails.

*Recommendation: test any new subscriptions with a test group from Tableau Server. This avoids sending a bad test run to actual business users.
