import streamlit as st
import pandas as pd
import os
# function for calculating percent of aligned aa
def aligned_percent(frags):
    return len(re.findall(r'[A-Z]',frags))/(len(re.findall(r'-',frags))+len(re.findall(r'[A-Z]',frags)))

# function for calculating ration between aligned aa and inserted aa
def letter_percent(frags):
    return (len(re.findall(r'[A-Za-z]',frags)))/len(re.findall(r'[A-Z]',frags))

# function for region filtration - step 1 in pipline step 3
def region_filtration(df):
    #bring all values into a single format
    df['Model_ID'] = df['Model_ID'].apply(lambda x: int(x) if isinstance(x, str) and x[0] == '0' else x)
    # Filter region alignments that contain only gaps.
    df = df[df['Region_coords'].notnull()]
    # Create region start coordinate column.
    df['region_first'] = df['Region_coords'].apply(lambda x: int(x.split('-')[0]))
    # Sort regions for each protein and model by value from column "region_first"
    df = df.sort_values(by=['REBASE_name', 'Model_ID', 'region_first'])
    # calculating percent of aligned aa
    df['aligned_percent'] = df['Alignment_frags'].apply(lambda x: aligned_percent(x))
    # function for calculating ration between aligned aa and inserted aa
    df['letter_percent'] = df['Alignment_frags'].apply(lambda x: letter_percent(x))
    # filter aligned_percent more than 0.4
    df = df[df['aligned_percent'] > 0.4]
    # filter aligned_percent more than 2.5
    df = df[df['letter_percent'] < 2.5]
    # filter not full-length sam_motif
    df = df[~((df['Region_name'] == 'sam_motif') & ((df['aligned_percent'] < 0.75) | (df['Alignment_frags'].str.count('-') > 1)))]
    # filter not full-length sam_motif
    df = df[~((df['Region_name'] == 'cat_motif') & ((df['aligned_percent'] < 0.75) | (df['Alignment_frags'].str.count('-') > 1)))]
    return df

# function for region filtration - step 2 in pipline step 3
def sequence_filtration(df):
    # for each region and name merge all coordinates
    df1 = df.groupby(['REBASE_name', 'Region_name'], as_index=False).agg([
        lambda x: ",".join(set(re.sub('\.', '', str(i)) for i in x))
    ])
    # manipulation with table
    df1 = df1.reset_index()
    df1.columns = df1.columns.droplevel(1)

    # select sequence with two or more cat-motifs
    dfcat = df1[(df1['Region_name'] == 'cat_motif') & (df1['Region_coords'].str.count(',') > 0)][
        ['REBASE_name', 'Region_coords', 'Alignment_frags', 'region_first']]
    # select sequence with two  or more cat-motifs
    dfsam = df1[(df1['Region_name'] == 'sam_motif') & (df1['Region_coords'].str.count(',') > 0)][
        ['REBASE_name', 'Region_coords', 'Alignment_frags', 'region_first']]
    # select sequence with two  or more cat-motifs and sequence with two or more cat-motifs
    dfcatsam = dfcat.merge(dfsam, on='REBASE_name', suffixes=('_cat', '_sam')).filter(regex="^(?!region_first)")
    return df[~df['REBASE_name'].isin(dfcatsam['REBASE_name'])], dfcatsam

#filter out region sets where Hu2-S1 or Hd2-Hd1 in the start.
#Hu2-S1 or Hd2-Hd1 could not be at the beginning of the sequence as they should follow cat- or sam-motif
def filter_dublicates_1(x, y):
    reg = x.split(',')
    if reg[0] == 'Hu2-S1' and reg.count('Hu2-S1') > 1:
        return ','.join(reg[1:])
    if reg[0] == 'Hd2-Hd1' and reg.count('Hd2-Hd1') > 1:
        return ','.join(reg[1:])
    else:
        return x

#filter out region sets where Hu2-S1 or Hd2-Hd1 at the beginning of the sequence.
#Hu2-S1 or Hd2-Hd1 could at the beginning of the sequence as they should follow cat- or sam-motif
def filter_dublicates_2(x, y):
    reg = x.split(',')
    if reg[0] == 'Hu2-S1' and reg.count('Hu2-S1') > 1:
        return ','.join(y.split(',')[1:])
    if reg[0] == 'Hd2-Hd1' and reg.count('Hd2-Hd1') > 1:
        return ','.join(y.split(',')[1:])
    else:
        return y

#filter out region sets where Hd3-S5 or S7-S4 at the end of the sequence.
#Hd3-S5 or S7-S4 could not be at the end of the sequence as they should be followed sam- or cat-motif
def filter_dublicates_3(x, y):
    reg = x.split(',')
    if reg[-1] == 'Hd3-S5' and reg.count('Hd3-S5') > 1:
        return ','.join(reg[:-1])
    if reg[-1] == 'S7-S4' and reg.count('S7-S4') > 1:
        return ','.join(reg[:-1])
    else:
        return x

#filter out region sets where Hd3-S5 or S7-S4 at the end of the sequence.
#Hd3-S5 or S7-S4 could not be at the end of the sequence as they should be followed sam- or cat-motif
def filter_dublicates_4(x, y):
    reg = x.split(',')
    if reg[-1] == 'Hu2-S1' and reg.count('Hu2-S1') > 1:
        return ','.join(y.split(',')[:-1])
    if reg[-1] == 'S7-S4' and reg.count('S7-S4') > 1:
        return ','.join(y.split(',')[:-1])
    else:
        return y
    
# function for making set of regions - step 3 in pipline step 3
def set_of_regions(df):
    # for each region and model merge all coordinates, region names, aligned percent
    df = df[['REBASE_name', 'Model_ID', 'Region_name', 'Region_coords', 'aligned_percent']].groupby(
        ['REBASE_name', 'Model_ID'], as_index=False).agg([
        lambda x: ",".join(str(i) for i in x)
    ])
    # manipulation with table
    df = df.reset_index()
    df.columns = df.columns.droplevel(1)

    #filter region names that comtain only one sam-motif and only one cat-motif
    df = df[(df['Region_name'].str.count('sam_motif') == 1) & (df['Region_name'].str.count('cat_motif') == 1)]

    #cut out false regions
    df['Region1'] = df.apply(lambda x: filter_dublicates_1(x['Region_name'], x['Region_coords']), axis=1)
    df['Region_coord1'] = df.apply(lambda x: filter_dublicates_2(x['Region_name'], x['Region_coords']), axis=1)
    df['Regions'] = df.apply(lambda x: filter_dublicates_3(x['Region1'], x['Region_coord1']), axis=1)
    df['Region_coords'] = df.apply(lambda x: filter_dublicates_4(x['Region1'], x['Region_coord1']), axis=1)
    df = df[['REBASE_name', 'Model_ID', 'Regions', 'Region_coords', 'aligned_percent']]
    
    #count number of regions-1
    df['Region_count'] = df['Regions'].str.count(',')

    #calculate average aligned percent for all regions
    df['Aligned_percent'] = df['aligned_percent'].apply(
        lambda x: sum([float(x) for x in x.split(',')]) / len(x.split(',')))
    return df

#function for choosing best profile  - step 4 in pipline step 3
def best_profile(df):
    df2 = df[df.groupby(["REBASE_name"])["Region_count"].transform(max) == df["Region_count"]]
    df3 = df2.merge(df2.groupby(["REBASE_name"])["Aligned_percent"].max().reset_index())
    return df3

#function for class assignment - step 5 in pipline step 3
def assign_class(model_id, regions, region_coords):
    if model_id in [54378, 51816, 52618, 53087] and regions.count(',') > 2:
        return 'A'
    if model_id in [36976, 37952, 45988, 48856, 52484] and regions.count(',') > 2:
        if regions.find('cat_motif') < regions.find('sam_motif'):
            return 'B'
        if regions.find('cat_motif') > regions.find('sam_motif'):
            if 'Hd2-Hd1' in regions and 'S7-S4' in regions:
                if int(region_coords.split(',')[regions.split(',').index('S7-S4')].split('-')[0]) - \
                int(region_coords.split(',')[regions.split(',').index('Hd2-Hd1')].split('-')[-1]) < 50:
                    return 'L'
                else:
                    return 'D'
            else:
                return 'D'
    if model_id in [46303, 46923, 45633] and regions.count(',') > 2:
        if regions[:3] == 'Hd3':
            return 'K'
        else:
            return 'C'
    if model_id in ["New-MTase-profile"] and regions.count(',') > 2:
        return "I"
    if model_id in ["Dam"] and regions.count(',') > 2:
        return "E"
    if model_id in ["EcoRI_methylase"] and regions.count(',') > 2:
        return "F"
    if model_id in ["MT-A70"] and regions.count(',') > 2:
        return "G"
    return '-'

def main():
    df = pd.read_csv('./pipelineFiles/region_alignments.tsv', sep='\t')
    #step 1 in pipline step 3
    df = region_filtration(df)
    # step 2 in pipline step 3
    t = sequence_filtration(df)
    t[1].to_csv('./pipelineFiles/several_cat_domains.tsv', sep='\t')
    # step 3 in pipline step 3
    df = set_of_regions(t[0])
    # step 4 in pipline step 3
    df = best_profile(df)
    # step 5 in pipline step 3
    df['New_class'] = df.apply(lambda x: assign_class(x[1], x[2], x[3]), axis=1)
    df.to_csv('./pipelineFiles/class.tsv', sep='\t')

##step 1
#os.system('python3 -m pip install -e etsv')
st.write('# MTase detection and classification pipeline')
st.sidebar.title("Pipeline steps")
st.sidebar.write('## Step 1')
uploaded_file = st.sidebar.file_uploader("Load sequences in fasta format")
if uploaded_file is not None:
    with open(os.path.join(".",uploaded_file.name),"wb") as f:
         f.write(uploaded_file.getbuffer())
    print(os.path.join(".",uploaded_file.name))                                
    os.system('hmmsearch --cpu 3 -E 0.01 --domE 0.01 --incE 0.01 --incdomE 0.01 \
        -o /dev/null --noali -A ./pipelineFiles/file.stk\
        ./pipelineFiles/selected_profiles.hmm ' + os.path.join(".",uploaded_file.name))
    st.sidebar.write('Step 1 finished')
    st.sidebar.write('## Step 2')
    os.system('rm ' + os.path.join(".",uploaded_file.name))                             
    os.system('./pipelineFiles/get_aln_regions.py \
    ./pipelineFiles/All_profile_region.csv \
    ./pipelineFiles/file.stk > ./pipelineFiles/region_alignments.tsv')
    st.dataframe(pd.read_csv('./pipelineFiles/region_alignments.tsv', sep='\t'))
    st.sidebar.write('Step 2 finished')
    st.sidebar.write('## Step 3')
    #st.write(os.system('chmod 777 ./pipelineFiles/classification.py'))
    st.write(os.system('./pipelineFiles/classification.py'))
    main()
    st.dataframe(pd.read_csv('./pipelineFiles/class.tsv', sep='\t'))

    st.dataframe(pd.read_csv('./pipelineFiles/several_cat_domains.tsv', sep='\t'))