from airflow.hooks.base_hook import BaseHook
from airflow.contrib.operators.slack_webhook_operator import SlackWebhookOperator


SLACK_CONN_ID = 'slack-coffeebiscuits'

def task_failure_alert(context):
	slack_webhook_token = BaseHook.get_connection(SLACK_CONN_ID).password
	slack_msg = """
			:red_circle: Tableau Subscription Failed. 
			*Task*: {task}  
			*Dag*: {dag} 
			*Execution Time*: {exec_date}  
			*Log Url*: {log_url} 
			""".format(
			task=context.get('task_instance').task_id,
			dag=context.get('task_instance').dag_id,
			ti=context.get('task_instance'),
			exec_date=context.get('execution_date'),
			log_url=context.get('task_instance').log_url,
	)
	failed_alert = SlackWebhookOperator(
		task_id='slack_test',
		http_conn_id='slack-coffeebiscuits',
		webhook_token=slack_webhook_token,
		message=slack_msg,
		username='airflow',
	)
	return failed_alert.execute(context=context)

def task_success_alert(context):
	slack_webhook_token = BaseHook.get_connection(SLACK_CONN_ID).password
	slack_msg = """
			:heavy_check_mark: Tableau Subscription Succeeded! 
			*Task*: {task}  
			*Dag*: {dag} 
			*Execution Time*: {exec_date}  
			*Log Url*: {log_url} 
			""".format(
			task=context.get('task_instance').task_id,
			dag=context.get('task_instance').dag_id,
			ti=context.get('task_instance'),
			exec_date=context.get('execution_date'),
			log_url=context.get('task_instance').log_url,
	)
	failed_alert = SlackWebhookOperator(
		task_id='slack_test',
		http_conn_id='slack-coffeebiscuits',
		webhook_token=slack_webhook_token,
		message=slack_msg,
		username='airflow'
	)
	return failed_alert.execute(context=context)
