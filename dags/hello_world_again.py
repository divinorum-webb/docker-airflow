from airflow import DAG
from airflow.operators.bash_operator import BashOperator
from airflow.operators.python_operator import PythonOperator
from airflow.operators.sensors import ExternalTaskSensor
from airflow.utils.trigger_rule import TriggerRule
from datetime import datetime, timedelta
from modules.outside_module import print_from_module
from tableau.slack_notifications import task_success_alert, task_failure_alert


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2019, 1, 1)
}

with DAG(
    'hello_world_again',
    default_args=default_args,
    catchup=False,
    schedule_interval='0 7 * * *',
    max_active_runs=1
) as dag:

    wait_first_job = ExternalTaskSensor(
        task_id='wait_tableau_subscriptions',
        external_dag_id='tableau_subscriptions_example',
        external_task_id='end_scorecard_subscriptions',
        trigger_rule='all_done'
    )

    start_hello_world_again = BashOperator(
        task_id='start_hello_world_again',
        bash_command="echo 'STARTING HELLO WORLD AGAIN SAMPLE'"
    )

    print_hello_world_again = BashOperator(
        task_id='print_hello_world_again',
        bash_command="echo 'Hello there, you little world, AGAIN'",
        on_success_callback=task_success_alert,
        on_failure_callback=task_failure_alert
    )

    print_outside_message = PythonOperator(
        task_id='print_outside_message',
        python_callable=print_from_module
    )

    end_hello_world_again = BashOperator(
        task_id='end_hello_world_again',
        bash_command="echo 'ENDING HELLO WORLD AGAIN SAMPLE'"
    )

    wait_first_job >> start_hello_world_again >> print_hello_world_again >> print_outside_message >> end_hello_world_again
    # start_hello_world_again >> print_hello_world_again >> print_outside_message >> end_hello_world_again
