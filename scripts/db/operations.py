from datetime import datetime
from typing import Union
from pandas import DataFrame

from gql import gql

from scripts.db.graphql import client, dump
from scripts.utils import print_red
from scripts.db import columns


def create_one(table_name: str, data: Union[dict, list, DataFrame]):
    if type(data) is DataFrame:
        data = data.to_dict(orient="records")
    req_str = \
        rf"""mutation {{
            create{table_name}(input: {dump(data)}) {{
                id
            }}
        }}"""
    req = gql(req_str)
    resp = client.execute(req)
    print(resp)
    return resp


def delete_one(table_name: str, id: str):
    print(id)
    req_str = \
        rf"""mutation {{
            delete{table_name}(input: {{id: "{id}"}}) {{
                id
            }}
        }}"""
    print(req_str)
    req = gql(req_str)
    resp = client.execute(req)
    print(resp)
    return resp


def list_items(table_name: str, cols: list = None) -> DataFrame:
    if cols is None:
        cols = columns[table_name]
    query_name = f"list{table_name}"
    if query_name[-1] == 'y':
        query_name = query_name[:-1] + "ies"
    else:
        query_name += "s"
    req_str = \
        rf"""query {{
            {query_name} {{
                items {{
                    {' '.join(cols)}
                }}
            }}
        }}"""
    req = gql(req_str)
    return DataFrame(client.execute(req)[query_name]['items'])


def query_equal(table_name: str, key, value):
    cols = columns[table_name]
    req_str = \
        rf"""query {{
            {table_name}(where: {{{key}: {{_eq: "{value}"}}}}) {{
                {' '.join(cols)}
            }}
        }}"""
    df = DataFrame(client.execute(gql(req_str))[table_name], columns=cols)
    if 'datetime' in cols:
        df['datetime'] = df['datetime'].apply(lambda x: datetime.fromisoformat(x))
    return df


def query_equal_open_close_time(table_name: str, key, value, open_time: datetime, close_time: datetime):
    cols = columns[table_name]
    req_str = \
        rf"""query {{
            {table_name}(where: {{{key}: {{_eq: "{value}"}},
            datetime: {{_gte: "{open_time.isoformat()}"}}, datetime: {{_lte: "{close_time.isoformat()}"}}}},
            order_by: {{close_time: asc}}) {{
                {' '.join(cols)}
            }}
        }}"""
    df = DataFrame(client.execute(gql(req_str))[table_name], columns=cols)
    if 'datetime' in cols:
        df['datetime'] = df['datetime'].apply(lambda x: datetime.fromisoformat(x))
    return df


def join_table(df: DataFrame, other_table: str, project_id: int):
    """Joins data from other_table onto given data

    Args:
        :param df: DataFrame to extend
        :param other_table: Table name from which data has to be joined
        :param project_id: ID of the project/asset"""

    other_df = query_equal_open_close_time(other_table, "project_id", project_id,
                                           df.iloc[0]['open_time'], df.iloc[-1]['close_time'])

    if len(other_df) == 0:
        symbol = query_equal("projects", "id", project_id)[0]['symbol']
        print_red(f"[CORE][ERROR] No {other_table} for {symbol} found in core.join_table()")
        return df

    df = df.set_index('close_time')
    other_df.drop(columns=['open_time'], inplace=True)
    df = df.join(other_df.set_index('close_time'), on='close_time')
    return df.reset_index()
