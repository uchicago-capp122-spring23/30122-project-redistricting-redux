'''
All functions in this file by: Matt Jackson
'''
import pandas as pd
import geopandas as gpd
import numpy as np
from collections import OrderedDict
from ast import literal_eval

SUPPORTED_STATES = OrderedDict({'Arizona': "AZ",
                                'Georgia': "GA",
                                'Nevada': "NV",
                                'North Carolina': "NC"})

def select_state(state_input=None, init_neighbors=False, affix_neighbors=True):
    '''
    Function that generalizes input to multiple states. To be used when we
    have multiple states. This will eventually evolve into what runs from
    the command line.

    Inputs:
        -none, requests input from user
    Returns (geopandas GeoDataFrame), indirectly, by calling helper
    '''
    while state_input not in SUPPORTED_STATES.values():
        state_input = input("Type a two-letter state postal abbreviation, or type 'list' to see list of supported states: ")
        if state_input == 'list':
            print("Here's a list of states currently supported by the program:")
            print(SUPPORTED_STATES)
        elif state_input in {'quit', 'exit', 'esc', 'escape', 'halt', 'stop'}:
            break
        elif state_input not in SUPPORTED_STATES.values():
            print("That's not the postal code of a state we currently have data for.")
    #get value from key source: https://www.adamsmith.haus/python/answers/how-to-get-a-key-from-a-value-in-a-dictionary
    state_fullname = [k for k, v in SUPPORTED_STATES.items() if v == state_input][0]
    print(f"You typed: {state_input} (for {state_fullname})")
    
    return import_state(state_input, init_neighbors, affix_neighbors)


def import_state(state_input, init_neighbors=False, affix_neighbors=True):
    '''
    Helper function that actually imports the state after selecting it.

    Inputs:
        -state_input (str): 2-letter state postal code abbreviation
    Returns (geopandas GeoDataFrame)
    '''
    state_fullname = [k for k, v in SUPPORTED_STATES.items() if v == state_input][0] #DRY

    print(f"Importing {state_fullname} 2020 Redistricting Data Hub data...")
    fp = f"merged_shps/{state_input}_VTD_merged.shp"
    state_data = gpd.read_file(fp)
    if "Tot_2020_t" in state_data.columns:
        state_data.rename(columns={"Tot_2020_t","POP100"})
        print("Renamed population column to POP100")
    print(f"{state_input} 2020 Redistricting Data Hub shapefile data imported")
    if init_neighbors:
        set_precinct_neighbors(state_data, state_input)
        print("Precinct neighbors calculated")
    if affix_neighbors: #maybe figure out how to do these as command line flags
        neighbor_fp = f'merged_shps/{state_input}_2020_neighbors.csv'
        affix_neighbors_list(state_data, neighbor_fp)
        print("Neighbors list affixed from file")
    state_data['dist_id'] = None

    return state_data   


def set_precinct_neighbors(df, state_postal):
    '''
    Creates a list of neighbors (adjacency list) for each precinct/VTD whose 
    geometry is in the GeoDataFrame.
    Takes about 80-90 seconds for the Georgia 2018 precinct map, or about .03
    seconds per precinct.

    Inputs:
        -df (GeoPandas GeoDataFrame): state data by precinct/VTD
        -state_postal (2-character string): postal code for a state supported
        by the program, e.g. "GA" for Georgia

    Returns: None, modifies df in-place
    '''
    #Inspired by:
    #https://gis.stackexchange.com/questions/281652/finding-all-neighbors-using-geopandas
    df['neighbors'] = None
    
    for index, row in df.iterrows():
        neighbors = np.array(df[df.geometry.touches(row['geometry'])].GEOID20)
        #maybe there's a way to update neighbors for all the neighbors this one finds too? to speed up/reduce redundant calcs?
        overlap = np.array(df[df.geometry.overlaps(row['geometry'])].GEOID20)
        if len(overlap) > 0:
            neighbors = np.union1d(neighbors, overlap)
        #If you convert to tuple here, later procedures to find available neighbors can use sets instead of lists
        #(np.array is an unhashable type)
        df.at[index, 'neighbors'] = neighbors
        if index % 100 == 0:
            print(f"Neighbors for precinct {index} calculated")
    
    print("Saving neighbors list to csv so you don't have to do this again...")
    df['neighbors'].to_csv(f'merged_shps/{state_postal}_2020_neighbors.csv')


def affix_neighbors_list(df, neighbor_filename):
    '''
    Affix an adjacency list of neighbors to the appropriate csv.

    Input:
        -df(geopandas GeoDataFrame): precinct/VTD-level data for a state
        -neighbor_filename (str): name of file where neighbors list is

    Returns: None, modifies df in-place
    '''
    neighbor_csv = pd.read_csv(neighbor_filename)
    neighbor_list = neighbor_csv['neighbors']
    #deserialize 
    df['neighbors'] = neighbor_list
    df['neighbors'] = df['neighbors'].apply(lambda x: 
                                            np.array(literal_eval(x.replace("\n", "").replace("' '", "', '")),
                                            dtype=object))