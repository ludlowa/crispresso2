#!/usr/bin/env python
'''
CRISPResso2 - Kendell Clement and Luca Pinello 2018
Software pipeline for the analysis of genome editing outcomes from deep sequencing data
(c) 2018 The General Hospital Corporation. All Rights Reserved.
'''


import logging
import multiprocessing as mp
import signal
import subprocess as sb
from functools import partial
import numpy as np
import pandas as pd

def run_crispresso(crispresso_cmds,descriptor,idx):
    """
    Runs a specified crispresso command specified by idx
    Used for multiprocessing by run_crispresso_cmds
    input:
    crispresso_cmds: list of commands to run
    descriptor: label printed out describing a command e.g. "Could not process 'region' 5" or "Could not process 'batch' 5"
    idx: index of the command to run
    """
    crispresso_cmd=crispresso_cmds[idx]

    logging.info('Running CRISPResso on %s #%d/%d: %s' % (descriptor, idx+1, len(crispresso_cmds), crispresso_cmd))

    return_value = sb.call(crispresso_cmd,shell=True)

    if return_value == 137:
        logging.warn('CRISPResso was killed by your system (return value %d) on %s #%d: "%s"\nPlease reduce the number of processes (-p) and run again.'%(return_value,descriptor,idx,crispresso_cmd))
    elif return_value != 0:
        logging.warn('CRISPResso command failed (return value %d) on %s #%d: "%s"'%(return_value,descriptor,idx,crispresso_cmd))
    else:
        logging.info('Finished CRISPResso %s #%d' %(descriptor,idx+1))
    return return_value

def run_crispresso_cmds(crispresso_cmds,n_processes=1,descriptor = 'region',continue_on_fail=False):
    """
    input: crispresso_cmds: list of crispresso commands to run
    info_cmd: info command from parent (logger)
    descriptor: label printed out describing a command e.g. "Could not process 'region' 5" or "Could not process 'batch' 5"
    """
    logging.info("Running CRISPResso with %d processes" % n_processes)
    pool = mp.Pool(processes = n_processes)
    idxs = range(len(crispresso_cmds))
    pFunc = partial(run_crispresso,crispresso_cmds,descriptor)

    #handle signals -- bug in python 2.7 (https://stackoverflow.com/questions/11312525/catch-ctrlc-sigint-and-exit-multiprocesses-gracefully-in-python)
    original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGINT, original_sigint_handler)
    try:
        res = pool.map_async(pFunc,idxs)
        ret_vals = res.get(60*60*10) # Without the timeout this blocking call ignores all signals.
        for idx, ret in enumerate(ret_vals):
            if ret == 137:
                raise Exception('CRISPResso %s #%d was killed by your system. Please decrease the number of processes (-p) and run again.'%(descriptor,idx))
            if ret != 0 and not continue_on_fail:
                raise Exception('CRISPResso %s #%d failed'%(descriptor,idx))
    except KeyboardInterrupt:
        pool.terminate()
        logging.warn('Caught SIGINT. Program Terminated')
        raise Exception('CRISPResso2 Terminated')
        exit (0)
    except Exception as e:
        print('CRISPResso2 failed')
        raise e
    else:
        plural = descriptor+"s"
        if descriptor.endswith("ch") or descriptor.endswith("sh"):
            plural = descriptor+"es"
        logging.info("Finished all " + plural)
        pool.close()
    pool.join()

def run_pandas_apply_parallel(input_df, input_function_chunk, n_processes=1):
    """
    Runs a function on chunks of the input_df
    This is a little clunky, but seems to work better than serial runs
    The input_function should be a wrapper that takes in df chunks and applies a real function on the rows
    For example, the input_function should be:
    def input_function_chunk(df):
        return df.apply(input_function,axis=1)
    or this (apply runs the function twice on the first row -- this loop doesn't)
    def input_function_chunk(df):
        new_df = pd.DataFrame(columns=df.columns)
        for i in range(len(df)):
            new_df = new_df.append(input_function(df.iloc[i].copy()))
        return(new_df)

    The wrapped function should add to rows and return the row
    e.g.  def input_function(row):
            row['newval'] = row['oldval']*row['oldval2']
            return row
    This is useful for functions for which the operation on the row takes a significant amount of time and the overhead
        of dataframe manipulation is relatively small
    """
    #shuffle the dataset to avoid finishing all the ones on top while leaving the ones on the bottom unfinished
    n_splits = min(n_processes,len(input_df))
    df_split = np.array_split(input_df.sample(frac=1),n_splits)
    pool = mp.Pool(processes = n_splits)

    #handle signals -- bug in python 2.7 (https://stackoverflow.com/questions/11312525/catch-ctrlc-sigint-and-exit-multiprocesses-gracefully-in-python)
    original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGINT, original_sigint_handler)
    try:
        df_new = pd.concat(pool.map(input_function_chunk,df_split))
    except KeyboardInterrupt:
        pool.terminate()
        logging.warn('Caught SIGINT. Program Terminated')
        raise Exception('CRISPResso2 Terminated')
        exit (0)
    except Exception as e:
        print('CRISPResso2 failed')
        raise e
    else:
        pool.close()
    pool.join()
    return df_new
