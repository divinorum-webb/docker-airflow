from airflow import DAG
from airflow.operators.bash_operator import BashOperator
from airflow.operators.python_operator import PythonOperator
from airflow.operators.dagrun_operator import TriggerDagRunOperator
from airflow.utils.trigger_rule import TriggerRule
from datetime import datetime, timedelta

from tableau.subscription_classes import *
from tableau.config import tableau_server_config, subscription_email_config
from tableau.slack_notifications import task_success_alert, task_failure_alert


default_args = {
	'owner': 'airflow',
	'depends_on_past': False,
	'start_date': datetime(2019, 1, 1)
}

with DAG(
	'tableau_subscription_example',
	default_args=default_args,
	catchup=False,
    schedule_interval='0 7 * * *'
) as dag:

	start_scorecard_subscriptions = BashOperator(
		task_id='start_subscriptions',
		bash_command="echo 'START TABLEAU SUBSCRIPTION EMAIL PROCESS'"
	)

	start_subscription_example = BashOperator(
		task_id='start_subscription_example',
		bash_command="echo 'KICKING OFF THE DEMO SUBSCRIPTION TASK'"
	)

	execute_subscription_example = PythonOperator(
		task_id='execute_subscription_example',
		provide_context=True,
		python_callable=send_subscription,
		params={
			'tableau_config': tableau_server_config,
			'subscription_config': subscription_email_config,
			'tableau_group': 'InterWorks - Airflow Demo',
			'workbook_name': 'InterWorks - Demo - Custom Subscriptions',
			'workbook_view': 'Superstore Demo',
			'email_subject': 'Custom Email Subscription from Airflow',
			'attachment_name': 'Superstore Demo Dashboard'
		},
		on_failure_callback=task_failure_alert,
		on_success_callback=task_success_alert
	)

	end_subscription_example = BashOperator(
		task_id='end_subscription_example',
		bash_command="echo 'WRAP IT UP, B'"
	)

	shameless_promotion = BashOperator(
		task_id='shameless_promotion',
		bash_command="echo 'OTHER EMAIL SUBSCRIPTION TASKS COULD FOLLOW THIS DEMO'"
	)

	end_scorecard_subscriptions = BashOperator(
		task_id='end_scorecard_subscriptions',
		bash_command="echo 'END TABLEAU SUBSCRIPTION EMAIL PROCESS'"
	)

	# trigger_next = TriggerDagRunOperator(
	# 	task_id='start_hello_world_again',
	# 	trigger_dag_id='hello_world_again'
	# )

	start_scorecard_subscriptions >> start_subscription_example >> execute_subscription_example >> end_subscription_example
	# end_subscription_example >> shameless_promotion >> end_scorecard_subscriptions >> trigger_next
	end_subscription_example >> shameless_promotion >> end_scorecard_subscriptions


