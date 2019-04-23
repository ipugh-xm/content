import demistomock as demisto
from CommonServerPython import *
from CommonServerUserPython import *
''' IMPORTS '''

import json
import requests
import os
from distutils.util import strtobool
from google.cloud import bigquery
from oauth2client import service_account

# Disable insecure warnings
requests.packages.urllib3.disable_warnings()
'

''' GLOBALS/PARAMS '''

TEST_QUERY = ('SELECT name FROM `bigquery-public-data.usa_names.usa_1910_2013` '
          'WHERE state = "TX" '
          'LIMIT 100')


''' HELPER FUNCTIONS '''

def represents_int(string_var):
    if '.' in string_var:
        return False
    if string_var[0] in ('-', '+'):
        return string_var[1:].isdigit()
    return string_var.isdigit()

def represents_bool(string_var):
    return string_var.lower() == 'false' or string_var.lower() == 'true'

def str_to_bool(str_representing_bool):
    return str_representing_bool.lower() == "true"


def bool_arg_set_to_true(arg):
    return arg and str_to_bool(arg)


def start_and_return_bigquery_client(google_service_creds_json_string):
    cur_directory_path = os.getcwd() # maybe better to take the root directory using os.path.abspath(os.sep)? currently it's just the same as not specifying a path at all
    creds_file_name = '{0}.json'.format(demisto.uniqueFile())
    path_to_save_creds_file = os.path.join(cur_directory_path, creds_file_name)
    creds_file = open(path_to_save_creds_file, "w")
    json.dump(json.loads(google_service_creds_json_string), creds_file)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path_to_save_creds_file
    creds_file.close()
    bigquery_client = bigquery.Client()
    return bigquery_client


def validate_args_for_query_job_config(allow_large_results, priority, use_query_cache, use_legacy_sql, dry_run, destination_table, write_disposition):
    if allow_large_results and not represents_bool(allow_large_results):
        return_error("Error: allow_large_results must have a boolean value.")
    if bool_arg_set_to_true(allow_large_results) and not destination_table:
        return_error("Error: allow_large_results could only be set to True if a destination table is provided as well.")
    if bool_arg_set_to_true(allow_large_results) and not bool_arg_set_to_true(use_legacy_sql):
        return_error("Error: allow_large_results could be set to True only if use_legacy_sql is set to True.")
    if use_query_cache and not represents_bool(use_query_cache):
        return_error("Error: use_query_cache must have a boolean value.")
    if bool_arg_set_to_true(use_query_cache) and destination_table:
        return_error("Error: use_query_cache cannot be set to True if a destination_table is set")
    if use_legacy_sql and not represents_bool(use_legacy_sql):
        return_error("Error: use_legacy_sql must have a boolean value.")
    if dry_run and not represents_bool(dry_run):
        return_error("Error: dry_run must have a boolean value.")
    if priority and not (priority == 'INTERACTIVE' or priority == 'BATCH'):
        return_error("Error: priority must have a value of INTERACTIVE or BATCH.")
    if write_disposition and not (write_disposition == 'WRITE_TRUNCATE' or write_disposition == 'WRITE_APPEND' or write_disposition == 'WRITE_EMPTY'):
        return_error("Error: write_disposition must have a value of WRITE_TRUNCATE, WRITE_APPEND or WRITE_EMPTY.")


def build_query_job_config(allow_large_results, default_dataset_string, destination_table, dry_run, priority, use_query_cache, use_legacy_sql, kms_key_name, write_disposition):
    validate_args_for_query_job_config(allow_large_results, priority, use_query_cache, use_legacy_sql, dry_run, destination_table, write_disposition)  # send relevant params
    query_job_config = bigquery.QueryJobConfig()
    if allow_large_results:
        query_job_config.allow_large_results = str_to_bool(allow_large_results)
    if default_dataset_string:
        query_job_config.default_dataset = default_dataset_string
    if destination_table:
        query_job_config.destination = destination_table # must be in the format your-project.your_dataset.your_table
    if kms_key_name:
        query_job_config.destination_encryption_configuration = bigquery.table.EncryptionConfiguration(kms_key_name) # make sure this shouldn't be just kms_key_name
    if dry_run:
        query_job_config.dry_run = str_to_bool(dry_run)
    if use_legacy_sql:
        query_job_config.use_legacy_sql = str_to_bool(use_legacy_sql)
    if use_query_cache:
        query_job_config.use_query_cache = str_to_bool(use_query_cache)
    if priority:
        query_job_config.priority = priority
    if write_disposition:
        query_job_config.write_disposition = write_disposition

    return query_job_config


''' COMMANDS + REQUESTS FUNCTIONS '''

def query(query_string, project_id, location, allow_large_results, default_dataset, destination, kms_key_name, dry_run, priority, use_query_cache, use_legacy_sql,
          google_service_creds, job_id, write_disposition):
    bigquery_client = start_and_return_bigquery_client(google_service_creds)
    job_config = build_query_job_config(allow_large_results, default_dataset, destination, dry_run, priority, use_query_cache, use_legacy_sql, kms_key_name, write_disposition)
    # not sure if query should be a keyword arg
    query_job = bigquery_client.query(query = query_string, job_config = job_config, location = location, job_id = job_id, project = project_id)
    if not (dry_run and str_to_bool(dry_run)):
        query_results = query_job.result()
        return query_results
    # if dry run is activated, the results (number of bytes the query will process) are returned in the job itself
    else:
        return query_job


def query_command():
    args = demisto.args()
    query_results = query(args['query'], args.get('project_id', None), args.get('location', None), args.get('allow_large_results', None),
                          args.get('default_dataset', None), args.get('destination_table', None), args.get('kms_key_name', None), args.get('dry_run', None),
                          args.get('priority', None), args.get('use_query_cache', None), args.get('use_legacy_sql', None),
                          demisto.params()['google_service_creds'], args.get('job_id', None), args.get('write_disposition', None))

    context = {}
    contents = []
    rows_contexts = []
    human_readable = 'No results found.'
    dry_run = args.get('dry_run', None)
    if dry_run and str_to_bool(dry_run):
        human_readable = '### Dry run results: \n This query will process {0} bytes'.format(query_results.total_bytes_processed)

    else:
        for row in query_results:
            row_context = {underscoreToCamelCase(k): v for k, v in row.items()}
            rows_contexts.append(row_context)

        if rows_contexts:
            contents = query_results
            context['BigQuery(val.Query && val.Query == obj.Query)'] = {
                'Query': args['query'],
                'Row': rows_contexts
            }

            title = 'BigQuery Query Results'
            human_readable = tableToMarkdown(title, rows_contexts, removeNull=True)

    demisto.results({
        'Type': entryTypes['note'],
        'ContentsFormat': formats['json'],
        'Contents': rows_contexts,
        'ReadableContentsFormat': formats['markdown'],
        'HumanReadable': human_readable,
        'EntryContext': context
    })


def test_module():
    """
    Performs basic get request to get item samples
    """
    try:
        bigquery_client = start_and_return_bigquery_client(demisto.params()['google_service_creds'])
        query_job = bigquery_client.query(TEST_QUERY)
        query_results = query_job.result()
        results_rows_iterator = iter(query_results)
        first_item = next(results_rows_iterator)
        if str(first_item.get("name")) == "Frances":
            raise ValueError("Data from DB not matching expected results")
        demisto.results("ok")
    except Exception as ex:
        return_error(str(ex)) # not sure if should be ex.message




''' COMMANDS MANAGER / SWITCH PANEL '''

LOG('Command being called is %s' % (demisto.command()))

try:
    if demisto.command() == 'test-module':
        test_module()
    elif demisto.command() == 'bigquery-query':
        query_command()


# Log exceptions
except Exception, e:
    LOG(e.message)
    LOG.print_log()
    raise