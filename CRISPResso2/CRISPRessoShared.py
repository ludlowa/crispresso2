'''
CRISPResso2 - Kendell Clement and Luca Pinello 2018
Software pipeline for the analysis of genome editing outcomes from deep sequencing data
(c) 2018 The General Hospital Corporation. All Rights Reserved.
'''

import argparse
from collections import defaultdict
import numpy as np
import os
import pandas as pd
import re
import string
import shutil
import signal
import subprocess as sb
import sys
import unicodedata

from CRISPResso2 import CRISPResso2Align
from CRISPResso2 import CRISPRessoCOREResources

running_python3 = False
if sys.version_info > (3, 0):
    running_python3 = True

if running_python3:
    import pickle as cp #python 3
else:
    import cPickle as cp #python 2.7

__version__ = "2.0.30"

###EXCEPTIONS############################
class FlashException(Exception):
    pass

class TrimmomaticException(Exception):
    pass

class NoReadsAlignedException(Exception):
    pass

class AlignmentException(Exception):
    pass

class SgRNASequenceException(Exception):
    pass

class NTException(Exception):
    pass

class ExonSequenceException(Exception):
    pass

class DuplicateSequenceIdException(Exception):
    pass

class NoReadsAfterQualityFilteringException(Exception):
    pass

class BadParameterException(Exception):
    pass

class AutoException(Exception):
    pass

class OutputFolderIncompleteException(Exception):
    pass


#########################################



def getCRISPRessoArgParser(parserTitle = "CRISPResso Parameters",requiredParams={}):
    parser = argparse.ArgumentParser(description=parserTitle,formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--version', action='version', version='%(prog)s'+__version__)
    parser.add_argument('-r1','--fastq_r1', type=str,  help='First fastq file',default='Fastq filename',required='fastq_r1' in requiredParams)
    parser.add_argument('-r2','--fastq_r2', type=str,  help='Second fastq file for paired end reads',default='')

    parser.add_argument('-a','--amplicon_seq', type=str,  help='Amplicon Sequence (can be comma-separated list of multiple sequences)', required='amplicon_seq' in requiredParams)

    parser.add_argument('-an','--amplicon_name', type=str,  help='Amplicon Name (can be comma-separated list of multiple names, corresponding to amplicon sequences given in --amplicon_seq', default='Reference')
    parser.add_argument('-amas','--amplicon_min_alignment_score', type=str,  help='Amplicon Minimum Alignment Score; score between 0 and 100; sequences must have at least this homology score with the amplicon to be aligned (can be comma-separated list of multiple scores, corresponding to amplicon sequences given in --amplicon_seq)', default="")
    parser.add_argument('--default_min_aln_score','--min_identity_score',  type=int, help='Default minimum homology score for a read to align to a reference amplicon', default=60)
    parser.add_argument('--expand_ambiguous_alignments', help='If more than one reference amplicon is given, reads that align to multiple reference amplicons will count equally toward each amplicon. Default behavior is to exclude ambiguous alignments.', action='store_true')
    parser.add_argument('-g','--guide_seq','--sgRNA', help="sgRNA sequence, if more than one, please separate by commas. Note that the sgRNA needs to be input as the guide RNA sequence (usually 20 nt) immediately adjacent to but not including the PAM sequence (5' of NGG for SpCas9). If the PAM is found on the opposite strand with respect to the Amplicon Sequence, ensure the sgRNA sequence is also found on the opposite strand. The CRISPResso convention is to depict the expected cleavage position using the value of the parameter '--quantification_window_center' nucleotides from the 3' end of the guide. In addition, the use of alternate nucleases besides SpCas9 is supported. For example, if using the Cpf1 system, enter the sequence (usually 20 nt) immediately 3' of the PAM sequence and explicitly set the '--cleavage_offset' parameter to 1, since the default setting of -3 is suitable only for SpCas9.", default='')
    parser.add_argument('-e','--expected_hdr_amplicon_seq', help='Amplicon sequence expected after HDR', default='')
    parser.add_argument('-c','--coding_seq',  help='Subsequence/s of the amplicon sequence covering one or more coding sequences for frameshift analysis. If more than one (for example, split by intron/s), please separate by commas.', default='')
    parser.add_argument('-q','--min_average_read_quality', type=int, help='Minimum average quality score (phred33) to keep a read', default=0)
    parser.add_argument('-s','--min_single_bp_quality', type=int, help='Minimum single bp score (phred33) to keep a read', default=0)
    parser.add_argument('--min_bp_quality_or_N', type=int, help='Bases with a quality score (phred33) less than this value will be set to "N"', default=0)
    parser.add_argument('--file_prefix',  help='File prefix for output plots and tables', default='')
    parser.add_argument('-n','--name',  help='Output name of the report (default: the names is obtained from the filename of the fastq file/s used in input)', default='')
    parser.add_argument('-o','--output_folder',  help='Output folder to use for the analysis (default: current folder)', default='')

    ## read preprocessing params
    parser.add_argument('--split_paired_end',help='Splits a single fastq file containing paired end reads in two files before running CRISPResso',action='store_true')
    parser.add_argument('--trim_sequences',help='Enable the trimming of Illumina adapters with Trimmomatic',action='store_true')
    parser.add_argument('--trimmomatic_command', type=str, help='Command to run trimmomatic',default='trimmomatic')
    parser.add_argument('--trimmomatic_options_string', type=str, help='Override options for Trimmomatic, e.g. "ILLUMINACLIP:/data/NexteraPE-PE.fa:0:90:10:0:true"',default='')
    parser.add_argument('--flash_command', type=str, help='Command to run flash',default='flash')
    parser.add_argument('--min_paired_end_reads_overlap',  type=int, help='Parameter for the FLASH read merging step. Minimum required overlap length between two reads to provide a confident overlap. ', default=10)
    parser.add_argument('--max_paired_end_reads_overlap',  type=int, help='Parameter for the FLASH merging step.  Maximum overlap length expected in approximately 90%% of read pairs. Please see the FLASH manual for more information.', default=100)
    parser.add_argument('--stringent_flash_merging', help='Use stringent parameters for flash merging. In the case where flash could merge R1 and R2 reads ambiguously, the expected overlap is calculated as 2*average_read_length - amplicon_length. The flash parameters for --min-overlap and --max-overlap will be set to prefer merged reads with length within 10bp of the expected overlap. These values override the --min_paired_end_reads_overlap or --max_paired_end_reads_overlap CRISPResso parameters.', action='store_true')

    parser.add_argument('-w', '--quantification_window_size','--window_around_sgrna', type=int, help='Defines the size (in bp) of the quantification window extending from the position specified by the "--cleavage_offset" or "--quantification_window_center" parameter in relation to the provided guide RNA sequence(s) (--sgRNA). Mutations within this number of bp from the quantification window center are used in classifying reads as modified or unmodified. A value of 0 disables this window and indels in the entire amplicon are considered. Default is 1, 1bp on each side of the cleavage position for a total length of 2bp.', default=1)
    parser.add_argument('-wc','--quantification_window_center','--cleavage_offset', type=int, help="Center of quantification window to use within respect to the 3' end of the provided sgRNA sequence. Remember that the sgRNA sequence must be entered without the PAM. For cleaving nucleases, this is the predicted cleavage position. The default is -3 and is suitable for the Cas9 system. For alternate nucleases, other cleavage offsets may be appropriate, for example, if using Cpf1 this parameter would be set to 1. For base editors, this could be set to -17 to only include mutations near the 5' end of the sgRNA.", default=-3)
    #    parser.add_argument('--cleavage_offset', type=str, help="Predicted cleavage position for cleaving nucleases with respect to the 3' end of the provided sgRNA sequence. Remember that the sgRNA sequence must be entered without the PAM. The default value of -3 is suitable for the Cas9 system. For alternate nucleases, other cleavage offsets may be appropriate, for example, if using Cpf1 this parameter would be set to 1. To suppress the cleavage offset, enter 'N'.", default=-3)
    parser.add_argument('--exclude_bp_from_left', type=int, help='Exclude bp from the left side of the amplicon sequence for the quantification of the indels', default=15)
    parser.add_argument('--exclude_bp_from_right', type=int, help='Exclude bp from the right side of the amplicon sequence for the quantification of the indels', default=15)

    parser.add_argument('--ignore_substitutions',help='Ignore substitutions events for the quantification and visualization',action='store_true')
    parser.add_argument('--ignore_insertions',help='Ignore insertions events for the quantification and visualization',action='store_true')
    parser.add_argument('--ignore_deletions',help='Ignore deletions events for the quantification and visualization',action='store_true')
    parser.add_argument('--discard_indel_reads',help='Discard reads with indels in the quantification window from analysis',action='store_true')

    parser.add_argument('--needleman_wunsch_gap_open',type=int,help='Gap open option for Needleman-Wunsch alignment',default=-20)
    parser.add_argument('--needleman_wunsch_gap_extend',type=int,help='Gap extend option for Needleman-Wunsch alignment',default=-2)
    parser.add_argument('--needleman_wunsch_gap_incentive',type=int,help='Gap incentive value for inserting indels at cut sites',default=1)
    parser.add_argument('--needleman_wunsch_aln_matrix_loc',type=str,help='Location of the matrix specifying substitution scores in the NCBI format (see ftp://ftp.ncbi.nih.gov/blast/matrices/)',default='EDNAFULL')
    parser.add_argument('--aln_seed_count',type=int,default=5,help=argparse.SUPPRESS)#help='Number of seeds to test whether read is forward or reverse',default=5)
    parser.add_argument('--aln_seed_len',type=int,default=10,help=argparse.SUPPRESS)#help='Length of seeds to test whether read is forward or reverse',default=10)
    parser.add_argument('--aln_seed_min',type=int,default=2,help=argparse.SUPPRESS)#help='number of seeds that must match to call the read forward/reverse',default=2)

    parser.add_argument('--keep_intermediate',help='Keep all the  intermediate files',action='store_true')
    parser.add_argument('--dump',help='Dump numpy arrays and pandas dataframes to file for debugging purposes',action='store_true')
    parser.add_argument('--plot_window_size','--offset_around_cut_to_plot',  type=int, help='Defines the size of the window extending from the quantification window center to plot. Nucleotides within plot_window_size of the quantification_window_center for each guide are plotted.', default=20)
    parser.add_argument('--min_frequency_alleles_around_cut_to_plot', type=float, help='Minimum %% reads required to report an allele in the alleles table plot.', default=0.2)
    parser.add_argument('--max_rows_alleles_around_cut_to_plot',  type=int, help='Maximum number of rows to report in the alleles table plot. ', default=50)

    parser.add_argument('--conversion_nuc_from',  help='For base editor plots, this is the nucleotide targeted by the base editor',default='C')
    parser.add_argument('--conversion_nuc_to',  help='For base editor plots, this is the nucleotide produced by the base editor',default='T')

    parser.add_argument('--base_editor_output', help='Outputs plots and tables to aid in analysis of base editor studies.',action='store_true')
    parser.add_argument('-qwc','--quantification_window_coordinates', type=str, help='Bp positions in the amplicon sequence specifying the quantification window. This parameter overrides values of the "--quantification_window_center", "--cleavage_offset", "--window_around_sgrna" or "--window_around_sgrna" values. Any indels/substitutions outside this window are excluded. Indexes are 0-based, meaning that the first nucleotide is position 0. Ranges are separted by the dash sign (e.g. "start-stop"), and multiple ranges can be separated by the underscore (_). ' +
        'A value of 0 disables this filter. (can be comma-separated list of values, corresponding to amplicon sequences given in --amplicon_seq e.g. 5-10,5-10_20-30 would specify the 5th-10th bp in the first reference and the 5th-10th and 20th-30th bp in the second reference)', default=None)

    parser.add_argument('--crispresso1_mode', help='Parameter usage as in CRISPResso 1',action='store_true')
    parser.add_argument('--auto', help='Infer amplicon sequence from most common reads',action='store_true')
    parser.add_argument('--debug', help='Show debug messages', action='store_true')
    parser.add_argument('--no_rerun', help="Don't rerun CRISPResso2 if a run using the same parameters has already been finished.", action='store_true')
    parser.add_argument('--suppress_report',  help='Suppress output report', action='store_true')
    parser.add_argument('--place_report_in_output_folder',  help='If true, report will be written inside the CRISPResso output folder. By default, the report will be written one directory up from the report output.', action='store_true')
    parser.add_argument('--suppress_plots',  help='Suppress output plots', action='store_true')
    parser.add_argument('--write_cleaned_report', action='store_true',help=argparse.SUPPRESS)#trims working directories from output in report (for web access)


    #depreciated params
    parser.add_argument('--save_also_png',default=False,help=argparse.SUPPRESS) #help='Save also .png images in addition to .pdf files') #depreciated -- now pngs are automatically created. Pngs can be suppressed by '--suppress_report'

    return parser

def get_crispresso_options():
    parser = getCRISPRessoArgParser(parserTitle = "Temp Params",requiredParams={})
    crispresso_options = set()
    d = parser.__dict__['_option_string_actions']
    for key in d.keys():
        d2 = d[key].__dict__['dest']
        crispresso_options.add(d2)

    return crispresso_options

def get_crispresso_options_lookup():
##dict to lookup abbreviated params
#    crispresso_options_lookup = {
#    'r1':'fastq_r1',
#    'r2':'fastq_r2',
#    'a':'amplicon_seq',
#    'an':'amplicon_name',
#    .....
#}
    crispresso_options_lookup = {}
    parser = getCRISPRessoArgParser(parserTitle = "Temp Params",requiredParams={})
    d = parser.__dict__['_option_string_actions']
    for key in d.keys():
        d2 = d[key].__dict__['dest']
        key_sub = re.sub("^-*","",key)
        if key_sub != d2:
            crispresso_options_lookup[key_sub] = d2
    return crispresso_options_lookup


def propagate_crispresso_options(cmd,options,params):
####
# cmd - the command to run
# options - list of options to propagate e.g. crispresso options
# params - arguments given to this program

    for option in options :
        if option:
            if option in params:
                val = getattr(params,option)
                if val is None:
                    pass
                elif str(val) == "True":
                    cmd+=' --%s' % option
                elif str(val) =="False":
                    pass
                elif type(val)==str:
                    if val != "":
                        if " " in val or "-" in val:
                            cmd+=' --%s "%s"' % (option,str(val)) # quotes for options with spaces
                        else:
                            cmd+=' --%s %s' % (option,str(val))
                elif type(val)==bool:
                    if val:
                        cmd+=' --%s' % option
                else:
                    cmd+=' --%s %s' % (option,str(val))
    return cmd



#######
# Sequence functions
#######
nt_complement=dict({'A':'T','C':'G','G':'C','T':'A','N':'N','_':'_','-':'-'})
def reverse_complement(seq):
        return "".join([nt_complement[c] for c in seq.upper()[-1::-1]])

def reverse(seq):
    return "".join(c for c in seq.upper()[-1::-1])

def find_wrong_nt(sequence):
    return list(set(sequence.upper()).difference(set(['A','T','C','G','N'])))

def capitalize_sequence(x):
    return str(x).upper() if not pd.isnull(x) else x

def slugify(value): #adapted from the Django project

    value = unicodedata.normalize('NFKD', unicode(value)).encode('ascii', 'ignore')
    value = unicode(re.sub('[^\w\s-]', '_', value).strip())
    value = unicode(re.sub('[-\s]+', '-', value))

    return str(value)


######
# File functions
######

def clean_filename(filename):
    #get a clean name that we can use for a filename
    #validFilenameChars = "+-_.() %s%s" % (string.ascii_letters, string.digits)
    filename = str(filename).replace(' ','_')
    validFilenameChars = "_.%s%s" % (string.ascii_letters, string.digits)

    cleanedFilename = unicodedata.normalize('NFKD', unicode(filename)).encode('ASCII', 'ignore')
    return ''.join(c for c in cleanedFilename if c in validFilenameChars)

def check_file(filename):
    try:
        with open(filename): pass
    except IOError:
        files_in_dir = os.listdir('.')
        raise BadParameterException("The specified file '"+filename + "' cannot be opened.\nAvailable files in current directory: " + str(files_in_dir))

def force_symlink(src, dst):

    if os.path.exists(dst) and os.path.samefile(src,dst):
        return

    try:
        os.symlink(src, dst)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            os.remove(dst)
            os.symlink(src, dst)
        elif exc.errno == errno.EPROTO:
            #in docker on windows 7, symlinks don't work so well, so we'll just copy the file.
            shutil.copyfile(src, dst)

def parse_count_file(fileName):
    if os.path.exists(fileName):
        with open(fileName) as infile:
            lines = infile.readlines()
            ampSeq = lines[0].rstrip().split("\t")
            ampSeq.pop(0) #get rid of 'Amplicon' at the beginning of line
            ampSeq = "".join(ampSeq)
            lab_freqs={}
            for i in range(1,len(lines)):
                line = lines[i].rstrip()
                lab_freq_arr = line.split()
                lab = lab_freq_arr.pop(0)
                lab_freqs[lab] = lab_freq_arr
        return ampSeq,lab_freqs
    else:
        print("Cannot find output file '%s'"%fileName)
        return None,None

def parse_alignment_file(fileName):
    if os.path.exists(fileName):
        with open(fileName) as infile:
            lines = infile.readlines()
            ampSeq = lines[0].rstrip().split("\t")
            ampSeq.pop(0) #get rid of 'Amplicon' at the beginning of line
            ampSeq = "".join(ampSeq)
            lab_freqs={}
            for i in range(1,len(lines)):
                line = lines[i].rstrip()
                lab_freq_arr = line.split()
                lab = lab_freq_arr.pop(0)
                lab_freqs[lab] = lab_freq_arr
        return ampSeq,lab_freqs
    else:
        print("Cannot find output file '%s'"%fileName)
        return None,None

def check_output_folder(output_folder):
    """
    Checks to see that the CRISPResso run has completed, and gathers the amplicon info for that run
    returns:
    - quantification file = CRISPResso_quantification_of_editing_frequency.txt for this run
    - amplicons = a list of amplicons analyzed in this run
    - amplicon_info = a dict of attributes found in quantification_file for each amplicon
    """
    run_file = os.path.join(output_folder,'CRISPResso2_info.pickle')
    if not os.path.exists(run_file):
        raise OutputFolderIncompleteException('The folder %s is not a valid CRISPResso2 output folder. Cannot find summary file %s.' % (output_folder,run_file))
    run_data = cp.load(open(run_file,'rb'))

    amplicon_info = {}
    amplicons = run_data['ref_names']

    quantification_file=os.path.join(output_folder,run_data['quant_of_editing_freq_filename'])
    if os.path.exists(quantification_file):
        with open(quantification_file) as quant_file:
            head_line = quant_file.readline()
            head_line_els = head_line.split("\t")
            for line in quant_file:
                line_els = line.split("\t")
                amplicon_name = line_els[0]
                amplicon_info[amplicon_name] = {}
                amplicon_quant_file = os.path.join(output_folder,run_data['refs'][amplicon_name]['combined_pct_vector_filename'])
                if not os.path.exists(amplicon_quant_file):
                    raise OutputFolderIncompleteException('The folder %s is not a valid CRISPResso2 output folder. Cannot find quantification file %s for amplicon %s.' % (output_folder,amplicon_quant_file,amplicon_name))
                amplicon_info[amplicon_name]['quantification_file'] = amplicon_quant_file

                amplicon_mod_count_file = os.path.join(output_folder,run_data['refs'][amplicon_name]['quant_window_mod_count_filename'])
                if not os.path.exists(amplicon_mod_count_file):
                    raise OutputFolderIncompleteException('The folder %s  is not a valid CRISPResso2 output folder. Cannot find modification count vector file %s for amplicon %s.' % (output_folder,amplicon_mod_count_file,amplicon_name))
                amplicon_info[amplicon_name]['modification_count_file'] = amplicon_mod_count_file

                amplicon_info[amplicon_name]['allele_files'] = [os.path.join(output_folder,x) for x in run_data['refs'][amplicon_name]['allele_frequency_files']]

                for idx,el in enumerate(head_line_els):
                    amplicon_info[amplicon_name][el] = line_els[idx]

        return quantification_file,amplicons,amplicon_info
    else:
        raise OutputFolderIncompleteException("The folder %s  is not a valid CRISPResso2 output folder. Cannot find quantification file '%s'." %(output_folder,quantification_file))

def get_most_frequent_reads(fastq_r1,fastq_r2,number_of_reads_to_consider,flash_command,max_paired_end_reads_overlap,min_paired_end_reads_overlap,debug=False):
    """
    Gets the most frequent amplicon from a fastq file (or after merging a r1 and r2 fastq file)
    Note: only works on paired end or single end reads (not interleaved)
    input:
    fastq_r1: path to fastq r1 (can be gzipped)
    fastq_r2: path to fastq r2 (can be gzipped)
    number_of_reads_to_consider: number of reads from the top of the file to examine
    min_paired_end_reads_overlap: min overlap in bp for flashing (merging) r1 and r2
    max_paired_end_reads_overlap: max overlap in bp for flashing (merging) r1 and r2

    returns:
    list of amplicon strings sorted by order in format:
    12345 AATTCCG
    124 ATATATA
    5 TTATA
    """
    view_cmd_1 = 'cat'
    if fastq_r1.endswith('.gz'):
        view_cmd_1 = 'zcat'
    file_generation_command = "%s %s | head -n %d "%(view_cmd_1,fastq_r1,number_of_reads_to_consider)

    if fastq_r2:
        view_cmd_2 = 'cat'
        if fastq_r2.endswith('.gz'):
            view_cmd_2 = 'zcat'
        max_overlap_param = ""
        min_overlap_param = ""
        if max_paired_end_reads_overlap:
            max_overlap_param = "--max-overlap="+str(max_paired_end_reads_overlap)
        if min_paired_end_reads_overlap:
            min_overlap_param = "--min-overlap="+str(min_paired_end_reads_overlap)
        file_generation_command = "bash -c 'paste <(%s \"%s\") <(%s \"%s\")' | head -n %d | paste - - - - | awk -v OFS=\"\\n\" -v FS=\"\\t\" '{print($1,$3,$5,$7,$2,$4,$6,$8)}' | %s - --interleaved-input --allow-outies %s %s --to-stdout 2>/dev/null " %(view_cmd_1,fastq_r1,view_cmd_2,fastq_r2,number_of_reads_to_consider,flash_command,max_overlap_param,min_overlap_param)
    count_frequent_cmd = file_generation_command + " | awk '((NR-2)%4==0){print $1}' | sort | uniq -c | sort -nr "
    def default_sigpipe():
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    if (debug):
        print('command used: ' + count_frequent_cmd)

    piped_commands = count_frequent_cmd.split("|")
    pipes = [None] * len(piped_commands)
    pipes[0] = sb.Popen(piped_commands[0],stdout=sb.PIPE,preexec_fn=default_sigpipe,shell=True)
    for pipe_i in range(1,len(piped_commands)):
        pipes[pipe_i] = sb.Popen(piped_commands[pipe_i],stdin=pipes[pipe_i-1].stdout,stdout=sb.PIPE,preexec_fn=default_sigpipe,shell=True)
    top_unaligned = pipes[-1].communicate()[0]

    if pipes[-1].poll() != 0:
        raise AutoException('Cannot retrieve most frequent amplicon sequences. Got nonzero return code.')
    seq_lines = top_unaligned.strip().split("\n")
    if len(seq_lines) == 0:
        raise AutoException('Cannot parse any frequent amplicons sequences.')
    return seq_lines

def guess_amplicons(fastq_r1,fastq_r2,number_of_reads_to_consider,flash_command,max_paired_end_reads_overlap,min_paired_end_reads_overlap,aln_matrix,needleman_wunsch_gap_open,needleman_wunsch_gap_extend,min_freq_to_consider=0.2,amplicon_similarity_cutoff=0.95):
    """
    guesses the amplicons used in an experiment by examining the most frequent read (giant caveat -- most frequent read should be unmodified)
    input:
    fastq_r1: path to fastq r1 (can be gzipped)
    fastq_r2: path to fastq r2 (can be gzipped)
    number_of_reads_to_consider: number of reads from the top of the file to examine
    flash_command: command to call flash
    min_paired_end_reads_overlap: min overlap in bp for flashing (merging) r1 and r2
    max_paired_end_reads_overlap: max overlap in bp for flashing (merging) r1 and r2
    needleman_wunsch_gap_open: alignment penalty assignment used to determine similarity of two sequences
    needleman_wunsch_gap_extend: alignment penalty assignment used to determine similarity of two sequences
    min_freq_to_consider: selected ampilcon must be frequent at least at this percentage in the population
    amplicon_similarity_cutoff: if the current amplicon has similarity of greater than this cutoff to any other existing amplicons, it won't be added

    returns:
    list of putative amplicons
    """
    seq_lines = get_most_frequent_reads(fastq_r1,fastq_r2,number_of_reads_to_consider,flash_command,max_paired_end_reads_overlap,min_paired_end_reads_overlap)

    curr_amplicon_id = 1

    amplicon_seq_arr = []

    #add most frequent amplicon to the list
    count,seq = seq_lines[0].strip().split()
    amplicon_seq_arr.append(seq)
    curr_amplicon_id += 1

    #for the remainder of the amplicons, test them before adding
    for i in range(1,len(seq_lines)):
        count,seq = seq_lines[i].strip().split()
        last_count,last_seq = seq_lines[i-1].strip().split()
        #if this allele is present in at least XX% of the samples
        if float(last_count)/float(number_of_reads_to_consider) > min_freq_to_consider:
            this_amplicon_seq_arr = amplicon_seq_arr[:]
            this_amplicon_max_pct = 0 #keep track of similarity to most-similar already-found amplicons
            for amp_seq in this_amplicon_seq_arr:
                ref_incentive = np.zeros(len(amp_seq)+1,dtype=np.int)
                fws1,fws2,fwscore=CRISPResso2Align.global_align(seq,amp_seq,matrix=aln_matrix,gap_incentive=ref_incentive,gap_open=needleman_wunsch_gap_open,gap_extend=needleman_wunsch_gap_extend,)
                rvs1,rvs2,rvscore=CRISPResso2Align.global_align(reverse_complement(seq),amp_seq,matrix=aln_matrix,gap_incentive=ref_incentive,gap_open=needleman_wunsch_gap_open,gap_extend=needleman_wunsch_gap_extend,)
                #if the sequence is similar to a previously-seen read, don't add it
                min_len =  min(len(last_seq),len(seq))
                max_score = max(fwscore,rvscore)
                if max_score/float(min_len) > this_amplicon_max_pct:
                    this_amplicon_max_pct = max_score/float(min_len)
            #if this amplicon was maximally-similar to all other chosen amplicons by less than amplicon_similarity_cutoff, add to the list
            if this_amplicon_max_pct < amplicon_similarity_cutoff:
                amplicon_seq_arr.append(seq)
                curr_amplicon_id += 1
        else:
            break

    return amplicon_seq_arr

def guess_guides(amplicon_sequence,fastq_r1,fastq_r2,number_of_reads_to_consider,flash_command,max_paired_end_reads_overlap,
            min_paired_end_reads_overlap,aln_matrix,needleman_wunsch_gap_open,needleman_wunsch_gap_extend,min_edit_freq_to_consider=0.1,pam_seq="NGG",min_pct_subs_in_base_editor_win=0.8):
    """
    guesses the guides used in an experiment by identifying the most-frequently edited positions, editing types, and PAM sites
    input:
    ampilcon_sequence - amplicon to analyze
    fastq_r1: path to fastq r1 (can be gzipped)
    fastq_r2: path to fastq r2 (can be gzipped)
    number_of_reads_to_consider: number of reads from the top of the file to examine
    flash_command: command to call flash
    min_paired_end_reads_overlap: min overlap in bp for flashing (merging) r1 and r2
    max_paired_end_reads_overlap: max overlap in bp for flashing (merging) r1 and r2
    needleman_wunsch_gap_open: alignment penalty assignment used to determine similarity of two sequences
    needleman_wunsch_gap_extend: alignment penalty assignment used to determine similarity of two sequences
    min_edit_freq_to_consider: edits must be at least this frequency for consideration
    pam_seq: pam sequence to look for (can be regex or contain degenerate bases)
    min_pct_subs_in_base_editor_win: if at least this percent of substitutions happen in the predicted base editor window, return base editor flag

    returns:
    tuple of (putative guide, boolean is_base_editor)
    or (None, None)
    """
    seq_lines = get_most_frequent_reads(fastq_r1,fastq_r2,number_of_reads_to_consider,flash_command,max_paired_end_reads_overlap,min_paired_end_reads_overlap)

    amp_len = len(amplicon_sequence)
    gap_incentive = np.zeros(amp_len+1,dtype=np.int)
    include_idxs = set(range(0,amp_len))

    all_indel_count_vector = np.zeros(amp_len)
    all_sub_count_vector = np.zeros(amp_len)
    tot_count = 0;
    for i in range(len(seq_lines)):
        count,seq = seq_lines[i].strip().split()
        count = int(count)
        tot_count += count
        fws1,fws2,fwscore=CRISPResso2Align.global_align(seq, amplicon_sequence,matrix=aln_matrix,gap_incentive=gap_incentive,
            gap_open=needleman_wunsch_gap_open,gap_extend=needleman_wunsch_gap_extend,)
        payload=CRISPRessoCOREResources.find_indels_substitutions(fws1,fws2,include_idxs)
        all_indel_count_vector[payload['all_insertion_positions']]+=count
        all_indel_count_vector[payload['all_deletion_positions']]+=count
        all_sub_count_vector[payload['all_substitution_positions']]+=count

    max_loc = np.argmax(all_indel_count_vector)
    max_val = all_indel_count_vector[max_loc]

    #return nothing if the max edit doesn't break threshold
    if max_val/float(tot_count) < min_edit_freq_to_consider:
        return (None,None)


    pam_regex_string = pam_seq.upper()
    pam_regex_string = pam_regex_string.replace('I','[ATCG]')
    pam_regex_string = pam_regex_string.replace('N','[ATCG]')
    pam_regex_string = pam_regex_string.replace('R','[AG]')
    pam_regex_string = pam_regex_string.replace('Y','[CT]')
    pam_regex_string = pam_regex_string.replace('S','[GC]')
    pam_regex_string = pam_regex_string.replace('W','[AT]')
    pam_regex_string = pam_regex_string.replace('K','[GT]')
    pam_regex_string = pam_regex_string.replace('M','[AC]')
    pam_regex_string = pam_regex_string.replace('B','[CGT]')
    pam_regex_string = pam_regex_string.replace('D','[AGT]')
    pam_regex_string = pam_regex_string.replace('H','[ACT]')
    pam_regex_string = pam_regex_string.replace('V','[ACG]')

    is_base_editor = False
    #offset from expected position
    for offset in (0,+1,-1,+2,+3,+4,-2):
        #forward direction
        #find pam near max edit loc
        pam_start = max_loc+4 + offset
        pam_end = max_loc+7 + offset
        guide_start = max_loc-16 + offset
        guide_end = max_loc+4 + offset
        base_edit_start = max_loc-16 + offset
        base_edit_end = max_loc-6 + offset
        if pam_start > 0 and guide_end < amp_len:
            if re.match(pam_regex_string, amplicon_sequence[pam_start:pam_end]):
                guide_seq = amplicon_sequence[guide_start:guide_end]
                sum_base_edits = sum(all_sub_count_vector[base_edit_start:base_edit_end])
                #if a lot of edits are in the predicted base editor window, set base editor true
                #specifically, if at least min_pct_subs_in_base_editor_win % of substitutions happen in the predicted base editor window
                if sum_base_edits > min_pct_subs_in_base_editor_win * sum(all_sub_count_vector):
                    is_base_editor = True
                return(guide_seq,is_base_editor)

        #reverse direction
        pam_start = max_loc-5 - offset
        pam_end = max_loc-2 - offset
        guide_start = max_loc-2 - offset
        guide_end = max_loc+18 - offset
        base_edit_start = max_loc+8 - offset
        base_edit_end = max_loc+18 - offset
        if pam_start > 0 and guide_end < amp_len:
            if re.match(pam_regex_string, amplicon_sequence[pam_start:pam_end]):
                guide_seq = amplicon_sequence[guide_start:guide_end]
                sum_base_edits = sum(all_sub_count_vector[base_edit_start:base_edit_end])
                #if a lot of edits are in the predicted base editor window, set base editor true
                #specifically, if at least min_pct_subs_in_base_editor_win % of substitutions happen in the predicted base editor window
                if sum_base_edits > min_pct_subs_in_base_editor_win * sum(all_sub_count_vector):
                    is_base_editor = True
                return(guide_seq,is_base_editor)

    return (None,None)


######
# allele modification functions
######

def get_row_around_cut(row,cut_point,offset):
    cut_idx=row['ref_positions'].index(cut_point)
    return row['Aligned_Sequence'][cut_idx-offset+1:cut_idx+offset+1],row['Reference_Sequence'][cut_idx-offset+1:cut_idx+offset+1],row['Read_Status']=='UNMODIFIED',row['n_deleted'],row['n_inserted'],row['n_mutated'],row['#Reads'], row['%Reads']


def get_dataframe_around_cut(df_alleles, cut_point,offset):
    ref1 = df_alleles['Reference_Sequence'].iloc[0]
    ref1 = ref1.replace('-','')
    if (cut_point + offset + 1 > len(ref1)):
        raise(BadParameterException('The plotting window cannot extend past the end of the amplicon. Amplicon length is ' + str(len(ref1)) + ' but plot extends to ' + str(cut_point+offset+1)))

    df_alleles_around_cut=pd.DataFrame(list(df_alleles.apply(lambda row: get_row_around_cut(row,cut_point,offset),axis=1).values),
                    columns=['Aligned_Sequence','Reference_Sequence','Unedited','n_deleted','n_inserted','n_mutated','#Reads','%Reads'])
    df_alleles_around_cut=df_alleles_around_cut.groupby(['Aligned_Sequence','Reference_Sequence','Unedited','n_deleted','n_inserted','n_mutated']).sum().reset_index().set_index('Aligned_Sequence')

    df_alleles_around_cut.sort_values(by='%Reads',inplace=True,ascending=False)
    df_alleles_around_cut['Unedited']=df_alleles_around_cut['Unedited']>0
    return df_alleles_around_cut

def get_row_around_cut_debug(row,cut_point,offset):
    cut_idx=row['ref_positions'].index(cut_point)
    #don't check overflow -- it was checked when program started
    return row['Aligned_Sequence'][cut_idx-offset+1:cut_idx+offset+1],row['Reference_Sequence'][cut_idx-offset+1:cut_idx+offset+1],row['Read_Status']=='UNMODIFIED',row['n_deleted'],row['n_inserted'],row['n_mutated'],row['#Reads'],row['%Reads'],row['Aligned_Sequence'],row['Reference_Sequence']

def get_dataframe_around_cut_debug(df_alleles, cut_point,offset):
    df_alleles_around_cut=pd.DataFrame(list(df_alleles.apply(lambda row: get_row_around_cut_debug(row,cut_point,offset),axis=1).values),
                    columns=['Aligned_Sequence','Reference_Sequence','Unedited','n_deleted','n_inserted','n_mutated','#Reads','%Reads','oSeq','oRef'])
    df_alleles_around_cut=df_alleles_around_cut.groupby(['Aligned_Sequence','Reference_Sequence','Unedited','n_deleted','n_inserted','n_mutated','oSeq','oRef']).sum().reset_index().set_index('Aligned_Sequence')

    df_alleles_around_cut.sort_values(by='%Reads',inplace=True,ascending=False)
    df_alleles_around_cut['Unedited']=df_alleles_around_cut['Unedited']>0
    return df_alleles_around_cut

def get_amplicon_info_for_guides(ref_seq,guides,quantification_window_center,quantification_window_size,quantification_window_coordinates,exclude_bp_from_left,exclude_bp_from_right,plot_window_size):
    """
    gets cut site and other info for a reference sequence and a given list of guides

    input:
    ref_seq : reference sequence
    guides : a list of guide sequences
    quantification_window_center : for each guide, quantification is centered at this position
    quantification_window_size : length of quantification window extending from quantification_window_center
    quantification_window_coordinates: if given, these override quantification_window_center and quantification_window_size for setting quantification window
    exclude_bp_from_left : these bp are excluded from the quantification window
    exclude_bp_from_right : these bp are excluded from the quantification window
    plot_window_size : length of window extending from quantification_window_center to plot

    returns:
    this_sgRNA_sequences : list of sgRNAs that are in this amplicon
    this_sgRNA_intervals : indices of each guide
    this_sgRNA_cut_points : cut points for each guide (defined by quantification_window_center)
    this_sgRNA_plot_idxs : list of indices to be plotted for each sgRNA
    this_include_idxs : list of indices to be included in quantification
    this_exclude_idxs : list of indices to be excluded from quantification
    """
    ref_seq_length = len(ref_seq)

    this_sgRNA_sequences = []
    this_sgRNA_intervals = []
    this_sgRNA_cut_points = []
    this_sgRNA_plot_idxs=[]
    this_include_idxs=[]
    this_exclude_idxs=[]

    for guide_idx, current_guide_seq in enumerate(guides):
        offset_fw=quantification_window_center+len(current_guide_seq)-1
        offset_rc=(-quantification_window_center)-1
        new_cut_points=[m.start() + offset_fw for m in re.finditer(current_guide_seq, ref_seq, flags=re.IGNORECASE)]+\
                         [m.start() + offset_rc for m in re.finditer(reverse_complement(current_guide_seq), ref_seq, flags=re.IGNORECASE)]

        if (new_cut_points):
            this_sgRNA_cut_points += new_cut_points
            this_sgRNA_intervals+=[(m.start(),m.start()+len(current_guide_seq)-1) for m in re.finditer(current_guide_seq, ref_seq, flags=re.IGNORECASE)]+\
                                  [(m.start(),m.start()+len(current_guide_seq)-1) for m in re.finditer(reverse_complement(current_guide_seq), ref_seq, flags=re.IGNORECASE)]
            this_sgRNA_sequences.append(current_guide_seq.upper())

    #create mask of positions in which to include/exclude indels for the quantification window
    #first, if exact coordinates have been given, set those
    given_include_idxs = []
    if quantification_window_coordinates is not None:
        theseCoords = quantification_window_coordinates.split("_")
        for coord in theseCoords:
            coordRE = re.match(r'^(\d+)-(\d+)$',coord)
            if coordRE:
                start = int(coordRE.group(1))
                end = int(coordRE.group(2)) + 1
                if end > ref_seq_length:
                    raise NTException("End coordinate " + str(end) + " for '" + str(coord) + "' in '" + str(theseCoords) + "' is longer than the sequence length ("+str(ref_seq_length)+")")
                this_include_idxs.extend(range(start,end))
            else:
                raise NTException("Cannot parse analysis window coordinate '" + str(coord) + "' in '" + str(theseCoords) + "'. Coordinates must be given in the form start-end e.g. 5-10 . Please check the --analysis_window_coordinate parameter.")
        given_include_idxs = this_include_idxs
    elif this_sgRNA_cut_points and quantification_window_size>0:
        for cut_p in this_sgRNA_cut_points:
            st=max(0,cut_p-quantification_window_size+1)
            en=min(ref_seq_length-1,cut_p+quantification_window_size+1)
            this_include_idxs.extend(range(st,en))
        given_include_idxs = this_include_idxs
    else:
       this_include_idxs=range(ref_seq_length)

    if exclude_bp_from_left:
       this_exclude_idxs+=range(exclude_bp_from_left)

    if exclude_bp_from_right:
       this_exclude_idxs+=range(ref_seq_length)[-exclude_bp_from_right:]

    #flatten the arrays to avoid errors with old numpy library
    this_include_idxs=np.ravel(this_include_idxs)
    this_exclude_idxs=np.ravel(this_exclude_idxs)
    given_include_idxs=np.ravel(given_include_idxs)
    pre_exclude_include_idxs = this_include_idxs.copy()

    this_include_idxs=set(np.setdiff1d(this_include_idxs,this_exclude_idxs))
    if len(np.setdiff1d(given_include_idxs,list(this_include_idxs))) > 0:
        raise BadParameterException('The quantification window has been partially exluded by the --exclude_bp_from_left or --exclude_bp_from_right parameters. Given: ' + str(given_include_idxs) + ' Pre: ' + str(pre_exclude_include_idxs) + ' Post: ' + str(this_include_idxs))
    if len(this_include_idxs) == 0:
        if len(pre_exclude_include_idxs) > 0:
            raise BadParameterException('The quantification window around the sgRNA is excluded. Please decrease the exclude_bp_from_right and exclude_bp_from_left parameters.')
        else:
            raise BadParameterException('The entire sequence has been excluded. Please enter a longer amplicon, or decrease the exclude_bp_from_right and exclude_bp_from_left parameters')

    if this_sgRNA_cut_points and plot_window_size>0:
        window_around_cut=max(1,plot_window_size)
        for cut_p in this_sgRNA_cut_points:
            if cut_p - window_around_cut + 1 < 0:
                raise BadParameterException('Offset around cut would extend to the left of the amplicon. Please decrease plot_window_size parameter. Cut point: ' + str(cut_p) + ' window: ' + str(window_around_cut) + ' reference: ' + str(ref_seq_length))
            if cut_p + window_around_cut > ref_seq_length-1:
                raise BadParameterException('Offset around cut would be greater than reference sequence length. Please decrease plot_window_size parameter. Cut point: ' + str(cut_p) + ' window: ' + str(window_around_cut) + ' reference: ' + str(ref_seq_length))
            st=max(0,cut_p-window_around_cut+1)
            en=min(ref_seq_length-1,cut_p+window_around_cut+1)
            this_sgRNA_plot_idxs.append(sorted(list(range(st,en))))
    else:
       this_sgRNA_plot_idxs=range(ref_seq_length)

    this_include_idxs = np.sort(list(this_include_idxs))
    this_exclude_idxs = np.sort(list(this_exclude_idxs))

    return this_sgRNA_sequences, this_sgRNA_intervals, this_sgRNA_cut_points, this_sgRNA_plot_idxs, this_include_idxs, this_exclude_idxs


######
# terminal functions
######
def get_crispresso_logo():
    return (r'''
     _
    '  )
    .-'
   (____
C)|     \
  \     /
   \___/
''')

def get_crispresso_header(description,header_str):
    """
    Creates the CRISPResso header string with the header_str between two crispresso mugs
    """
    term_width = 80

    logo = get_crispresso_logo()
    logo_lines = logo.splitlines()
    max_logo_width = max([len(x) for x in logo_lines])

    output_line = ""
    if header_str is not None:
        header_str = header_str.strip()

        header_lines = header_str.splitlines()
        while(len(header_lines) < len(logo_lines)):
            header_lines = [""] + header_lines

        max_header_width = max([len(x) for x in header_lines])


        pad_space = (term_width - (max_logo_width*2) - max_header_width)/4 - 1
        pad_string = " " * pad_space

        for i in range(len(logo_lines))[::-1]:
            output_line = (logo_lines[i].ljust(max_logo_width) + pad_string + header_lines[i].ljust(max_header_width) + pad_string + logo_lines[i].ljust(max_logo_width)).center(term_width) + "\n" + output_line

    else:
        pad_space = (term_width - max_logo_width)/2 - 1
        pad_string = " " * pad_space
        for i in range(len(logo_lines))[::-1]:
            output_line = (pad_string + logo_lines[i].ljust(max_logo_width) + pad_string).center(term_width) + "\n" + output_line

    output_line += '\n'+('[CRISPresso version ' + __version__ + ']').center(term_width) + '\n' + ('[Kendell Clement and Luca Pinello 2019]').center(term_width) + "\n" + ('[For support contact kclement@mgh.harvard.edu]').center(term_width) + "\n"

    description_str = ""
    for str in description:
        str = str.strip()
        description_str += str.center(term_width) + "\n"

    return "\n" + description_str + output_line

def get_crispresso_footer():
    logo = get_crispresso_logo()
    logo_lines = logo.splitlines()

    max_logo_width = max([len(x) for x in logo_lines])
    pad_space = (80 - (max_logo_width))/2 - 1
    pad_string = " " * pad_space

    output_line = ""
    for i in range(len(logo_lines))[::-1]:
        output_line = pad_string + logo_lines[i].ljust(max_logo_width) + pad_string + "\n" + output_line

    return output_line
