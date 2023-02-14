#print("Importing geopandas...")
import geopandas as gpd
import numpy as np
import random #SINCE YOU USE RANDOM YOU NEED TO SET A SEED SOMEWHERE FOR REPLICABILITY
import re
import time
from datetime import datetime
import matplotlib as plt

def startup():
    '''
    Get the GA 2018 data ready to do things with.
    Inputs:
        -none
    Returns: none, loads ga_data as the df
    '''
    print("Importing Georgia 2018 precinct shapefile data...")
    fp = "openprecincts_ga_2018/2018Precincts.shp"
    ga_data = gpd.read_file(fp)
    print("Georgia 2018 shapefile data imported")
    #ga_data['neighbors'] = None
    print("Calculating district neighbors:")
    set_precinct_neighbors(ga_data)
    print("District neighbors calculated")
    ga_data['dist_id'] = None #use .isnull() to select all of these

    #This should write the geodataframe *back out* so you don't have to run it
    #every time

    return ga_data


def clear_district_drawings(df):
    '''
    Clears off any district IDs that precincts may have been assigned in the
    past. Good idea to call this before calling any map-drawing function.
    Inputs:
        df (geopandas GeoDataFrame)
    Returns: None, modifies GeoDataFrame in-place
    '''
    df['dist_id'] = None


###STATS FUNCTION###

def population_sum(df, colname, district=None):
    '''
    Calculates the total population across a state df, or district therein, of 
    all people designated a given way in a column. 'district' flag allows for
    calling this function on specific districts once they're drawn.
    Note that values can get weird due to floating points, so I round.

    Inputs:
        -df (Geopandas GeoDataFrame) 
        -col (str): name of a column in the data
        -district (any): district ID. If None, calculates total for whole state
    Returns (int): Total population
    '''
    if district is not None:
        df = df[df.dist_id == district]

    return int(df[colname].sum())


def blue_red_margin(df, dcol, rcol, district=None):
    '''
    Returns the difference in votes, normalized to percentage points, between
    the Democratic candidate and the Republican candidate in the given area.
    Should only be called using candidates who actually ran against each other
    in the same race during the same election cycle.
    Inputs: 
        -df (Geopandas GeoDataFrame)
        -dcol (str): name of the column in the data representing the Democratic
        candidate's votes earned.
        -rcol (str): name of the column in the data representing the Republican
        candidate's votes earned.
        -district (any): district ID. If None, calculates margin for the whole
        state.
    Returns (float): number between -1.0 and 1.0, representing the difference
    (1.0 means the Democratic candidate got 100% of the vote and the Republican
    got 0%, for a margin of victory of 100 percentage points; -1.0 means the
    Republican candidate got 100% of the vote and the Democrat got 0%. An 
    exactly tied race will result in 0.0)
    '''
    blue_total = population_sum(df, dcol, district)
    red_total = population_sum(df, rcol, district)

    try:
        return (blue_total - red_total) / (blue_total + red_total)
    except ZeroDivisionError:
        return 0.0


def target_dist_pop(df, n=14):
    '''
    Determine how many people should live in each district in a map where each
    district has an equal number of people, given its total population.

    Inputs:
        -df (GeoPandas GeoDataFrame)
        -n (int): number of districts to draw (for Georgia, this number is
        currently 14)
    Returns (int): Target population value 
    '''
    #gonna have to change what "tot" is named based on data source
    return population_sum(df, "tot") // n

###DRAWING-RELATED FUNCTIONS###

def set_precinct_neighbors(df):
    '''
    Creates a list of neighbors for each precinct whose geometry is in the 
    GeoDataFrame.

    Inputs:
        -df (GeoPandas GeoDataFrame)

    Returns: None, modifies df in-place
    '''
    #Inspired by:
    #https://gis.stackexchange.com/questions/281652/finding-all-neighbors-using-geopandas
    df['neighbors'] = None
    
    #This is real slow, takes maybe 2 minutes for voting precincts
    for index, row in df.iterrows():
        neighbors = np.array(df[df.geometry.touches(row['geometry'])].loc_prec)
        #maybe there's a way to update neighbors for all the neighbors this one finds too? to speed up/reduce redundant calcs?
        #print(len(neighbors))
        overlap = np.array(df[df.geometry.overlaps(row['geometry'])].loc_prec)
        if len(overlap) > 0:
            #print(f"FOUND {len(overlap)} OVERLAPS!!!!")
            neighbors = np.union1d(neighbors, overlap)

        #print(neighbors)
        df.at[index, 'neighbors'] = neighbors
        if index % 100 == 0:
            print(f"Neighbors for precinct {index} calculated")

    #print(df['neighbors'])

def draw_into_district(df, precinct, id):
    '''
    Assigns a subunit of the state (currently, voting precinct; ideally, census
    block) to a district. The district is a property of the row of the df, 
    rather than a spatially joined object, at least for now.
    Will get called repeatedly by district drawing methods.

    Inputs:
        -df (GeoPandas GeoDataFrame):
        -precinct(str): ID of the precinct to find and draw into district.
        -id (anything, but probably int): Name or number of the district to be
        drawn into.

    Returns: Nothing, modifies df in-place
    '''
    #warning: there are three fewer loc_prec than rows in the 2018 dataset
    df.loc[df['loc_prec'] == precinct, 'dist_id'] = id



#can you set a keyword argument to output of another function?
#i.e. target_pop = target_dist_pop(df, 14)?
def draw_random_district(df, target_pop, id, curr_precinct=None):
    '''
    Draw a random district. Select a random starting precinct, use draw_into_district
    to give it a dist_id, then repeatedly call draw_into_district on random
    neighbors of precincts already in the district being drawn.

    Terminates if the district reaches a target population value, or if there
    are no eligible empty neighboring precincts to keep drawing into.

    Inputs:
        -df (geopandas GeoDataFrame): 
        -target-pop (int): target population of each district. When drawing a 
        state map, this will be 1/n, where n is the total population of the state
        as measured in the data.
        -id (any, usually int): The label to give precincts within the district.
        For a state map, this will usually be 1 for the first district drawn,
        2 for the second, etc.
        -curr_precinct (str): the current precinct being drawn into. When function
        is initialized without this keyword argument, it selects an empty precinct
        at random.
    '''
    if population_sum(df, 'tot', district=id) >= target_pop:
        print("Target population met or exceeded. Ending district draw")
        #time.sleep(0.5)
        return None #"break"
        #TODO: code in some level of allowable deviation

    if curr_precinct is None:
        #select a random precinct to start at
        #TODO: Need to make sure it's outside districts that have been drawn
        curr_index = random.randint(0, len(df)-1)
        curr_precinct = df.loc[curr_index, 'loc_prec']
        # #https://datatofish.com/random-rows-pandas-dataframe/
        # curr_precinct = df.sample()['loc_prec'] 
        # #i JUST want a string here, not df nonsense
        # #it's not letting me just take out the string value of loc_prec
        # #because it requires the row index to use .loc, and that's whatever random number instead of 0
        # print(str(curr_precinct))
        print(f"We're gonna start at: {curr_precinct}")
        #print(type(curr_precinct))
        #i think i have to do a neighbors check here or else start over
    else: 
        curr_index = df.index[df['loc_prec'] == curr_precinct].tolist()[0]
        print(f"We continue with: {curr_precinct}")

    if df.loc[curr_index, 'dist_id'] is None:
        print(f"Now drawing {curr_precinct} into district")
        draw_into_district(df, curr_precinct, id)
        print(f"Current district population: {population_sum(df, 'tot', district=id)}")

    all_neighbors = df.loc[curr_index, 'neighbors']
    #print(all_neighbors)
    #again i JUST want a string. jfc. 
    #link to index derping stuff i've been drawing on: 
    #https://stackoverflow.com/questions/21800169/python-pandas-get-index-of-rows-where-column-matches-certain-value
    # filter those down to neighbors whose dist_id is still None
    # consider redoing as an elegant list comprehension
    allowed_neighbors = []
    for nabe in all_neighbors:
        nabe_index = df.index[df['loc_prec'] == nabe].tolist()
        #print(nabe_index)
        if df.loc[nabe_index[0], 'dist_id'] is None:
            allowed_neighbors.append(nabe)
    #print(allowed_neighbors)
    #Handle case where there are no available neighbors to draw into
    if len(allowed_neighbors) == 0:
        print("No valid neighbors to draw into! Handling error case...")
 
        dist_so_far = [] + list(df[df.dist_id == id]['loc_prec'])
        #debug attempt: adding empty list so it's always a list

        #assert dist_so_far is not None, "dist_so_far is None"

        #handle the error if there are no valid neighbors and it's the first precinct for a new district
        if dist_so_far is None or len(dist_so_far) == 0:
            print("It looks like you can't start drawing here. Restarting somewhere else...")
            #time.sleep(0.5)
            draw_into_district(df, curr_precinct, None) #undo initial draw
            draw_random_district(df, target_pop, id)

        #handle the error where there are no neighbors of *any* point in district
        #This shouldn't print multiple times for one district, and yet it sometimes prints
        #two or three times
        if len(all_allowed_neighbors_of_district(df, id)) == 0:
            print("It is impossible to continue drawing a contiguous district. Stopping")
            time.sleep(0.2)
            return None

        #this picks from a neighbor that is guaranteed to be empty and allowed
        unstick_precinct = random.choice(all_allowed_neighbors_of_district(df, id))
        print(f"Trying again with {unstick_precinct} as resumption point")
        #time.sleep(0.1)
        #jumps to that precinct and tries again
        draw_random_district(df, target_pop, id, curr_precinct=unstick_precinct)
        #TODO: find some way to reference its "edges" to make this less shitty and bogosortish
    else:
    #select a neighbor at random and call this function again 
    #https://stackoverflow.com/questions/306400/how-can-i-randomly-select-an-item-from-a-list
        next_precinct = random.choice(allowed_neighbors)
        draw_random_district(df, target_pop, id, curr_precinct=next_precinct)


def all_allowed_neighbors_of_district(df, id):
    '''
    Ascertain if there are any allowed neighbors anywhere for a district. 
    If this returns a list of length 0, it is impossible to keep drawing a 
    contiguous district.
    '''
    nabe_set = set()
    nabes_so_far = list(df[df.dist_id == id]['neighbors']) #use np.union1d and set here
    for array in nabes_so_far:
        for nabe in array:
            nabe_set.add(nabe)
    #print(nabe_set)

    #helperize this
    allowed_neighbors = []
    for nabe in nabe_set:
        nabe_index = df.index[df['loc_prec'] == nabe].tolist()
        #print(nabe_index)
        if df.loc[nabe_index[0], 'dist_id'] is None:
            allowed_neighbors.append(nabe)

    return allowed_neighbors

def draw_random_state_map(df, num_districts):
    '''
    Uses draw_random_district() to draw a map of random districts of equal
    population for the whole state.
    FINISH DOCSTRING

    Inputs:
        -df (Geopandas GeoDataFrame): set of precincts or ideally census blocks
        for state
        -num_districts (int): Number of districts to draw (for Georgia, that's 14)
    '''
    #TODO: Finish this function
    target_pop = target_dist_pop(df, num_districts)
    for id in range(1, num_districts + 1):
        print(f"Now drawing district {id}...")
        time.sleep(0.2)
        draw_random_district(df, target_pop, id)
        #print(f"Filling holes in district {id}...")
        #fill_district_holes(df, id)

    #EXPORT SOMETHING SOMEWHERE SO MAP IS REPRODUCIBLE
    #maybe do something to add "orphan" precincts to the least populous nearby
    #district all at once at the end should be faster?

### PLOTTING FUNCTIONS ###

def plot_redblue_by_district(df, dcol, rcol, num_dists=14):
    '''
    Outputs a map of the state that color-codes each district by the partisan
    balance of its vote, i.e. dark blue if it overwhelmingly voted for Democrat,
    dark red if it overwhelmingly voted for Republican, and some neutral for if it
    was close to even.
    Call this only AFTER drawing a map of districts.
    FINISH DOCSTRING
    Inputs:
        -df (geopandas DataFrame): 
        -dcol (str): indicates name of geopandas column
        -rcol (str):
        -num_dists (int):
    Outputs:
        -plot as .png file in folder
    '''
    
    df['raw_margin'] = None
    for i in range(1, num_dists+1): #this should be doable on one line vectorized
        df.loc[df.dist_id == i, 'raw_margin'] = blue_red_margin(df, dcol, rcol, i)

    #TODO: figure out how to push legend off map, or maybe turn it into categorical color bar
    df.plot(column='raw_margin', cmap='seismic_r')
    #fig, ax = plt.subplots(1)
    #sm = plt.cm.ScalarMappable(cmap='seismic_r')
    #cbar = fig.colorbar(sm) #all of these extremely basic things from many matplotlib StackOverflow answers fail

    timestamp = datetime.now().strftime("%m%d-%H%M%S")
    filepath = 'maps/ga_testmap_' + timestamp
    plt.pyplot.savefig(filepath, dpi=200) 
    print(f"District map saved to {filepath}")
#Multiple possible kinds of plot:
    #-state map (choropleth colored by Kemp-Abrams or Biden-Trump margin)
    #-state map (choropleth colored by racial demographics)
    #-state map (random colors)
    #-bar chart (put statewide margin on dotted line on x axis, give each district a bar with its %D/%R vertically through it)
    #-bar chart (racial demographics)

def cleanup_map(df):
    '''
    Takes the initial output of draw_random_state_map and "cleans it up" so that
    all districts are contiguous, gapless, and of relatively even population
    size. 
    This may have to involve a while loop that goes through all unclaimed precincts
    repeatedly until they're all claimed, which would be slow af, or there may
    be a way to break it into helper functions that all target specific kinds of
    subdistricts
    '''
    #TODO: Fix "orphaned areas" surrounded by a district -- if there is a precinct
    #or cluster of precincts whose dist_id is None, and all surrounding area has 
    #the same dist_id, assign the orphaned precincts to the district surrounding them.
    
    #TODO possibly, if we care: Fix "orphaned districts" surrounded entirely by
    #a different district. (Note: This is one of the most obvious failure modes
    #by which draw_random_state_map produces districts that are way too small in
    #population and impossible to fill. If you can, adjust THAT function so its
    # "random" starting points are not trapped inside a different district --
    # or do the "orphaned areas" fix BEFORE starting to draw the next one

    #TODO: "population swaps" -- if there is a district whose total population is
    #too large (wthin something like 1% of even), and it borders a district whose
    #total population is too small, reassign neighboring precincts of the more populous
    #district to the less populous one until it is close to the target population
    pass

def get_all_holes(df):
    '''
    Get a dataframe of all precincts that have not yet been drawn into a district.
    Inputs:
        -df(geopandas GeoDataFrame)

    Returns (df object): set of precincts with all their attributes
    '''
    return df.loc[df['dist_id'].isnull()]

def fill_district_holes(df):
    '''
    District 'cleanup' helper function. If there are orphan precincts surrounded
    on all sides by a single district, assigns the orphaned precinct to
    that surrounding district.
    Inputs:
        -df (GeoPandas GeoDataFrame)
    Returns: None, modifies df in place
    '''
    #find precincts not yet drawn into a district
    holes = df.loc[df['dist_id'].isnull()]
    #print(holes)
    valid_holes = [] #list of district names to be drawn
    
    #narrow down those precincts to ones whose neighbors all have the same dist_id
    #OKAY NO. IT'S WAY TOO INEFFICIENT TO CALL THIS SEPARATELY FOR DISTINCT FUNCTIONS
    #FIX THAT
    for index, hole in holes.iterrows():
        districts_around_hole = find_neighboring_districts(df, hole['neighbors'])
        print(districts_around_hole)
        if len(districts_around_hole) == 1 and id in districts_around_hole:
            print("Just this district")
            valid_holes.append(hole['loc_prec'])
        #Let's try adding precincts that are adjoining this precinct and no others
        elif (len(districts_around_hole) == 2 and 
              id in districts_around_hole and
              None in districts_around_hole):
            print("Just this district and None")
            valid_holes.append(hole['loc_prec']) 

    print(f"The holes in this district are:{valid_holes}")

    for valid_hole in valid_holes:
        draw_into_district(df, valid_hole, id)
        print("Hole filled")

def fill_district_holes2(df):
    '''
    Screw it, we're just starting over.
    It's not efficient to generate all teh holes and then go one by once through
    dist_ids.
    Better to generate all the holes, then iterate across all holes and do
    something to them.
    
    Then maybe surround it with a while loop
    '''
    holes = df.loc[df['dist_id'].isnull()]
    for index, hole in holes.iterrows():
        districts_around_hole = find_neighboring_districts(df, hole['neighbors'])
        real_dists_ard_hole = {dist for dist in districts_around_hole if dist is not None}
        if len(real_dists_ard_hole) == 0: #i.e. if every neighbor of this hole is also a hole:
            pass #and handle in successive calls to this function
        elif len(real_dists_ard_hole) == 1: #i.e. if this borders or is inside exactly one district:
            neighbor_dist_id = int(list(real_dists_ard_hole)[0]) #extract that district id
            #THIS WILL BREAK IF YOU GIVE YOUR DISTRICTS ANY ID OTHER THAN INTEGERS
            draw_into_district(df, hole['loc_prec'], neighbor_dist_id)
        elif len(real_dists_ard_hole) >= 2: #i.e. if this could go into one of two other districts
            #a cleaner way to do this might involve finding the neighboring district
            #with least population and always drawing into that, so as to make the
            #pop-swap stuff to come later less onerous.
            neighbor_dist_id = random.choice(tuple(real_dists_ard_hole)) #pick one at random
            draw_into_district(df, hole['loc_prec'], neighbor_dist_id)




def find_neighboring_districts(df, lst):
    '''
    Helperizing this function. Takes in a list of precinct names, and 
    outputs a set of all districts those precincts have been drawn into.
    Inputs:
        -df: geopandas GeoDataFrame
        -lst (NumPy array): list of neighbors as found by df['neighbors']
    Returns (set): set of dist_ids
    '''
    set_of_dists_theyre_in = set()
    for precinct_name in lst:
        #extract the number of the district of each neighbor.
        the_dist_its_in = df.loc[df['loc_prec'] == precinct_name, 'dist_id'].iloc[0]
        #again, i JUST want the SINGLE INTEGER. JFC.
        set_of_dists_theyre_in.add(the_dist_its_in)
    return set_of_dists_theyre_in
    #consider changing this to not include None


def map_stats_table(df):
    '''
    Compresses the df down to a table of by-district stats, where each row
    represents entire area with one dist_id. e.g. population, racial demographics,
    Dem vote, Rep vote, and margin, for easier calling and plotting 
    '''
    #TODO: Implement this function
    pass

if __name__ == '__main__':
    ga_data = startup()
    print("Drawing random map:")
    draw_random_state_map(ga_data, 14)
    print("Plotting non-cleaned districts on state map:")
    plot_redblue_by_district(ga_data, "G18DGOV", "G18RGOV")
    print("Cleaning up districts one iteration...")
    fill_district_holes2(ga_data)
    print("Plotting cleaned districts on state map for contrast:")
    plot_redblue_by_district(ga_data, "G18DGOV", "G18RGOV")
    print("Clearing districts...")
    clear_district_drawings(ga_data)