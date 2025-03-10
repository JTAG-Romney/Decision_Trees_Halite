import copy
import json
import os
import os.path
from tqdm import tqdm
import zstd

import hlt
import config

ARBITRARY_ID = -1


def parse_replay_file(file_name):
    #print("Load Replay: " + file_name)
    player_name = get_winner_name(file_name).split(" ")[0]
    with open(file_name, 'rb') as f:
        data = json.loads(zstd.loads(f.read()))

    #print("Load Basic Information")
    player = [p for p in data['players'] if p['name'].split(" ")[0] == player_name][0]
    player_id = int(player['player_id'])
    my_shipyard = hlt.Shipyard(player_id, ARBITRARY_ID,
                               hlt.Position(player['factory_location']['x'], player['factory_location']['y']))
    other_shipyards = [
        hlt.Shipyard(p['player_id'], ARBITRARY_ID, hlt.Position(p['factory_location']['x'], p['factory_location']['y']))
        for p in data['players'] if int(p['player_id']) != player_id]
    width = data['production_map']['width']
    height = data['production_map']['height']

    #print("Load Cell Information")
    first_cells = []
    for x in range(len(data['production_map']['grid'])):
        row = []
        for y in range(len(data['production_map']['grid'][x])):
            row += [hlt.MapCell(hlt.Position(x, y), data['production_map']['grid'][x][y]['energy'])]
        first_cells.append(row)
    frames = []
    for f in data['full_frames']:
        prev_cells = first_cells if len(frames) == 0 else frames[-1]._cells
        new_cells = copy.deepcopy(prev_cells)
        for c in f['cells']:
            new_cells[c['y']][c['x']].halite_amount = c['production']
        frames.append(hlt.GameMap(new_cells, width, height))

    #print("Load Player Ships")
    moves = [{} if str(player_id) not in f['moves'] else {m['id']: m['direction'] for m in f['moves'][str(player_id)] if
                                                          m['type'] == "m"} for f in data['full_frames']]
    ships = [{} if str(player_id) not in f['entities'] else {
        int(sid): hlt.Ship(player_id, int(sid), hlt.Position(ship['x'], ship['y']), ship['energy']) for sid, ship in
        f['entities'][str(player_id)].items()} for f in data['full_frames']]

    #print("Load Other Player Ships")
    other_ships = [
        {int(sid): hlt.Ship(int(pid), int(sid), hlt.Position(ship['x'], ship['y']), ship['energy']) for pid, p in
         f['entities'].items() if
         int(pid) != player_id for sid, ship in p.items()} for f in data['full_frames']]

    #print("Load Droppoff Information")
    first_my_dropoffs = [my_shipyard]
    first_them_dropoffs = other_shipyards
    my_dropoffs = []
    them_dropoffs = []
    for f in data['full_frames']:
        new_my_dropoffs = copy.deepcopy(first_my_dropoffs if len(my_dropoffs) == 0 else my_dropoffs[-1])
        new_them_dropoffs = copy.deepcopy(first_them_dropoffs if len(them_dropoffs) == 0 else them_dropoffs[-1])
        for e in f['events']:
            if e['type'] == 'construct':
                if int(e['owner_id']) == player_id:
                    new_my_dropoffs.append(
                        hlt.Dropoff(player_id, ARBITRARY_ID, hlt.Position(e['location']['x'], e['location']['y'])))
                else:
                    new_them_dropoffs.append(
                        hlt.Dropoff(e['owner_id'], ARBITRARY_ID, hlt.Position(e['location']['x'], e['location']['y'])))
        my_dropoffs.append(new_my_dropoffs)
        them_dropoffs.append(new_them_dropoffs)
    return list(zip(frames, moves, ships, other_ships, my_dropoffs, them_dropoffs))



def process_f(folder_name,file_name):
   parsed_data =  parse_replay_file(os.path.join(folder_name, file_name))
   return parsed_data


from multiprocessing import Pool

def parse_replay_folder(folder_name, max_files=None):
    print("Parsing folder")
    replay_buffer = []
    result_list = []
    pool = Pool(config.CORES)
    for file_name in sorted(os.listdir(folder_name)):
        if not file_name.endswith(".hlt"):
            continue
        elif max_files is not None and len(replay_buffer) >= max_files:
            break
        else:
            result_list.append(pool.apply_async(process_f, args=(folder_name,file_name)))

    for p in tqdm(result_list):
        o = p.get()
        if o:
            replay_buffer.append(o)


    print("Replay Length: {}".format(len(replay_buffer)))
    print("Finished Parsing")
    return replay_buffer


def get_winner_name(file_path):
    #print("Loading:" + file_path)
    with open(file_path, "rb") as f:
        data = json.loads(zstd.loads(f.read()))
    total_turns = data["game_statistics"]["number_turns"]
    players = [{"id":item["player_id"],"rank":item["rank"]} for item in data["game_statistics"]["player_statistics"]]
    for rank in players:
        for player_object in data["players"]:
            if player_object["player_id"] == rank["id"]:
                rank = {**player_object, **rank}
            if rank["rank"] == 1:
                winner = rank
    #print("winer:", winner["name"])
    return winner["name"]
