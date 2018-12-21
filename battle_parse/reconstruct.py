# This file extracts information and a list of battle events from verbose battle logs

from tkinter import Tk

from util import log_parse
from .event import *
from . import model


# Load objects into scenario
def load_scenario(objs):
    scenario = model.Scenario()

    for obj in objs:
        if obj['_class_'] == 'com.cardhunter.battle.Battle':
            scenario.name = obj['scenarioName']
            scenario.display_name = obj['scenarioDisplayName']
            scenario.game_type = obj['gameType']
            scenario.audio_tag = obj['audioTag']
            scenario.room_name = obj['roomName']

        elif obj['_class_'] == 'com.cardhunter.battle.Player':
            player_index = obj['playerIndex']
            player = scenario.players[player_index]
            player.name = obj['playerName']
            player.rating = obj['rating']

        elif obj['_class_'] == 'com.cardhunter.battle.Square':
            scenario.map.add_square(obj['location.x'], obj['location.y'], obj['imageFlipX'], obj['imageFlipY'],
                                    obj['imageName'], obj['terrain'])

        elif obj['_class_'] == 'com.cardhunter.battle.Doodad':
            scenario.map.add_doodad(obj['displayPosition.x'], obj['displayPosition.y'], obj['imageFlipX'],
                                    obj['imageFlipY'], obj['imageName'], obj['marker'])

        elif obj['_class_'] == 'com.cardhunter.battle.ActorGroup':
            for group in scenario.players[0].groups + scenario.players[1].groups:
                if not group.is_described():
                    group.name = obj['name']
                    group.set_archetype(' '.join([obj['race'], obj['characterClass']]))
                    break

        elif obj['_class_'] == 'com.cardhunter.battle.ActorInstance':
            for group in scenario.players[0].groups + scenario.players[1].groups:
                if not group.is_described():
                    group.figure = obj['depiction']
                    group.audio_key = obj['audioKey']
                    group.x = obj['location.x']
                    group.y = obj['location.y']
                    group.fx = obj['facing.x']
                    group.fy = obj['facing.y']
                    break

    return scenario


# Extract extension events
def extension_events(scenario, extensions):
    events = []
    player_turn = 0
    must_discard = [-1, -1]
    for ex in extensions:
        ex_name = ex.get('_NAME')
        event_type = ex.get('type')

        if ex_name != 'battleTimer' and (ex_name != 'battle' or event_type == 'done'):
            continue

        print()
        print(ex)

        if ex_name == 'battleTimer':
            player_turn = ex['playerIndex']
            switch_player = ex['start']
            remaining = ex['timeRemaining']

            events.append(Timer(player_turn, switch_player, remaining))

        elif event_type == 'deckPeeksSent':
            events.append(DeckPeek(player_turn))

        elif event_type == 'handPeeksSent':
            events.append(HandPeek(player_turn))

        elif event_type == 'deckPeeks':
            # If the user is still unknown, use this deckPeeks to determine who it is
            if scenario.user is None:
                scenario.set_user(ex['SENDID'][0])

            # For every card in the peeks array, extract its info and append an event for it
            for info in ex['DP']['peeks']:
                original_player_index = info['cownerp']
                original_group_index = info['cownerg']
                card_index = info['card']
                item_name = info['origin']
                card_name = info['type']
                player_index = info['owner']
                group_index = info['group']

                events.append(CardDraw(player_turn, original_player_index, original_group_index, player_index,
                                         group_index, card_index, item_name, card_name))

        elif event_type == 'handPeeks':
            # For every card in the peeks array, extract its info and append an event for it
            for info in ex['HP']['peeks']:
                original_player_index = info['cownerp']
                original_group_index = info['cownerg']
                card_index = info['card']
                item_name = info['origin']
                card_name = info['type']
                player_index = info['owner']
                group_index = info['group']

                events.append(CardReveal(player_turn, original_player_index, original_group_index, player_index,
                                           group_index, card_index, item_name, card_name))

        elif event_type == 'action':
            # For every card in the peeks array, extract its info and append an event for it
            for info in ex['HP']['peeks']:
                original_player_index = info['cownerp']
                original_group_index = info['cownerg']
                card_index = info['card']
                item_name = info['origin']
                card_name = info['type']
                player_index = info['owner']
                group_index = info['group']

                events.append(CardPlay(player_turn, original_player_index, original_group_index, player_index,
                                         group_index, card_index, item_name, card_name))

                if 'TARP' in ex:
                    target_player_indices = ex['TARP']
                    target_group_indices = ex['TARG']

                    events.append(SelectTarget(player_turn, target_player_indices, target_group_indices))

        elif event_type == 'selectCard':
            # Discard during round
            if 'HP' in ex:
                for info in ex['HP']['peeks']:
                    original_player_index = info['cownerp']
                    original_group_index = info['cownerg']
                    card_index = info['card']
                    item_name = info['origin']
                    card_name = info['type']
                    player_index = info['owner']
                    group_index = info['group']

                    events.append(CardDiscard(player_turn, original_player_index, original_group_index, player_index,
                                                group_index, card_index, item_name, card_name))

            # Discard at end of round
            else:
                player_index = must_discard[0]
                group_index = must_discard[1]
                card_index = ex['sel']

                try:
                    card = scenario.players[player_index].groups[group_index].hand[card_index]
                    original_player_index = card.original_player_index
                    original_group_index = card.original_group_index
                    item_name = card.item_name
                    card_name = card.card_name
                except:
                    pass
                else:
                    events.append(CardDiscard(player_turn, original_player_index, original_group_index, player_index,
                                                group_index, card_index, item_name, card_name))

        # elif event_type == 'selectCards':
        #     if 'SELP' in ex:
        #         selected_player_indices = ex['SELP']
        #         selected_group_indices = ex['SELG']
        #         selected_card_indices = ex['SELCC']
        #         for i in range(len(selected_player_indices)):
        #             events.append(SelectEvent(player_turn, selected_player_indices[i], selected_group_indices[i],
        #                                       selected_card_indices[i]))

        elif event_type == 'mustDiscard':
            # Remember who must discard
            player_index = ex['PUI']
            group_index = ex['ACTG']

            must_discard[0] = player_index
            must_discard[1] = group_index

            events.append(MustDiscard(player_turn, player_index, group_index))

        elif event_type == 'noMoreDiscards':
            events.append(NoDiscards(player_turn))

        elif event_type == 'hasTrait':
            player_index = ex['PUI']

            events.append(MustPlayTrait(player_turn, player_index))

        elif event_type == 'noMoreTraits':
            events.append(NoTraits(player_turn))

        elif event_type in ('triggerFail', 'triggerSucceed') and 'TCLOC' in ex:
            die_roll = ex['TROLL']
            required_roll = ex['TTHRESH']
            hard_to_block = ex['TPEN']
            easy_to_block = ex['TBON']
            location = ex['TCLOC']

            if location == 0:
                player_index = ex['PUI']
                group_index = ex['ACTG']
                card_index = ex['ACTC']

                events.append(TriggerHand(player_turn, die_roll, required_roll, hard_to_block, easy_to_block, player_index,
                                            group_index, card_index))

            elif location == 1:
                player_index = ex['PUI']
                group_index = ex['ACTG']

                events.append(TriggerAttachment(player_turn, die_roll, required_roll, hard_to_block, easy_to_block,
                                                  player_index, group_index))

            elif location == 2:
                x = ex['TARX']
                y = ex['TARY']

                events.append(TriggerTerrain(player_turn, die_roll, required_roll, hard_to_block, easy_to_block, x, y))

        elif event_type == 'target':
            target_player_indices = ex['TARP']
            target_group_indices = ex['TARG']

            events.append(SelectTarget(player_turn, target_player_indices, target_group_indices))

        elif event_type == 'selectSquare':
            x = ex['TARX']
            y = ex['TARY']
            fx = ex['TARFX']
            fy = ex['TARFY']

            events.append(SelectSquare(player_turn, x, y, fx, fy))

        elif event_type == 'genRand':
            rands = ex['RAND']

            events.append(RNG(player_turn, rands))

        elif event_type == 'pass':
            events.append(Pass(player_turn))

        else:
            print('    | Ignored')

    return events


# Extract message events
def message_events(scenario, messages):
    events = []

    for msg in messages:
        print(msg)
        # TODO

    return events


# Form higher-level events
def refine_events(scenario, ex_events, msg_events):
    # TODO
    return ex_events


# Use the log text to construct a sequence of events that can be fed into a Battle
def load_battle(filename=None):
    # Load log contents into memory
    if filename is None:
        root = Tk()
        root.withdraw()
        try:
            log = root.clipboard_get()
        except:
            return None, None
    else:
        with open(filename) as f:
            log = f.read()

    # Find the most recent joinbattle
    log_lines = log.splitlines()
    try:
        first_line_index = len(log_lines) - 1 - log_lines[::-1].index('Received extension response: joinbattle')
    except:
        return None, None

    # Parse battle logs
    extensions, messages = log_parse.parse_battle('\n'.join(log_lines[first_line_index:]))
    joinbattle, extensions = extensions[0], extensions[1:]

    # Load objects into scenario
    scenario = load_scenario(joinbattle['objects'])

    if not scenario.is_described():
        pass  # Scenario not completely started

    # Extract extension events
    ex_events = extension_events(scenario, extensions)

    # Extract message events
    msg_events = message_events(scenario, messages)

    # Interpolate and extrapolate to form higher-level events
    events = refine_events(scenario, ex_events, msg_events)

    return events, scenario
