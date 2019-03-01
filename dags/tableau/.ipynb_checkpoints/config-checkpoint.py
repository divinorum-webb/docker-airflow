"""
Reference Notes

tableau_server_config details configuration for TableauServer class

'password' -> Note that this is NOT your AD password.
If you use your AD password, authentication will fail.
You will need to obtain your actual Tableau Server password for this.
For example, your AD password could be 'foo', but your Tableau Server password is 'bar'.
You probably need a Tableau Server Admin to help you set / discover your Tableau Server password.

'api_version' -> Change this value to match the API version which corresponds to the current Tableau Server version.
Look here to look up the appropriate api_version, given the current Tableau Server version: 
https://onlinehelp.tableau.com/current/api/rest_api/en-us/REST/rest_api_concepts_versions.htm

'cache_buster' -> This value references a dummy parameter within a Tableau Workbook file. 
We use this value when downloading images from Tableau Server so that the image returned is not a cached ancient relic of days past.
Your workbook needs a parameter whose name matches that of your 'cache_buster' name for this to work.

The subscription_email_config dict details configuration for the EmailSubscription class
"""

tableau_server_config = {
	'tableau_prod': {
        'server': 'https://tableaupoc.interworks.com',
        'api_version': '3.2',
        'username': 'estam',
        'password': 'Act1Andariel!',
        'site': 'estam',
        'cache_buster': 'Donut',
        'temp_dir': '/dags/tableau_subscriptions/temp/'
    }
}

subscription_email_config = {
    'default': {
        'smtp': {
            'username': 'elliott.stam@activision.com',
            'password': 'Divinorum800x!',
            'server': 'smtp.office365.com:587'
        },
        'assets': {
            'html_file': '/dags/tableau_subscriptions/assets/html_test.html'
        }
    }
}
