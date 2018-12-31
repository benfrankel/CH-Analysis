# This file extracts information and a list of battle events from verbose battle logs

from tkinter import Tk
import re

from util import log_parse
from .event import *
from . import model


# Load objects into battle
def load_battle_objects(objs):
    battle = model.Battle()

    for i, obj in enumerate(objs):
        if obj['_class_'].endswith('.Battle'):
            battle.scenario_name = obj['scenarioName']
            battle.display_name = obj['scenarioDisplayName']
            battle.room_name = obj['roomName']
            battle.room_id = obj['roomID']
            battle.time_limit = obj['timeLimit']
            battle.use_draw_limit = obj['enforceDrawLimit']
            battle.game_type = obj['gameType']  # TODO: What does this represent?
            battle.audio_tag = obj['audioTag']
            battle.current_turn = obj['activePlayer']
            battle.current_round = obj['turnNumber']
            battle.game_over = obj['gameOver']
            # TODO: obj['nextFirstPlayerIndex']?
            # TODO: obj['awaitingInstruction']?

        elif obj['_class_'].endswith('.Player'):
            player_index = obj['playerIndex']
            player = battle.players[player_index]
            player.name = obj['playerName']
            player.player_id = obj['playerID']
            player.user_id = obj['userID']
            player.rating = obj['rating']
            player.is_npc = obj['isNPC']
            player.stars = obj['score']
            player.stars_needed = obj['winningScore']
            player.cards_drawn = obj['cardsDrawnThisRound']
            player.draw_limit = obj['drawLimit']  # TODO: Is this -1 when there is no draw limit?
            # TODO: obj['moveStartTime']?
            # TODO: obj['side']?
            # TODO: obj['passingAsOf']?
            # TODO: obj['defeated']?

        elif obj['_class_'].endswith('.Square'):
            battle.map.add_square(
                x=obj['location.x'],
                y=obj['location.y'],
                flip_x=obj['imageFlipX'],
                flip_y=obj['imageFlipY'],
                image_name=obj['imageName'],
                terrain=obj['terrain'],
            )

        elif obj['_class_'].endswith('.Doodad'):
            battle.map.add_doodad(
                x=obj['displayPosition.x'],
                y=obj['displayPosition.y'],
                flip_x=obj['imageFlipX'],
                flip_y=obj['imageFlipY'],
                image_name=obj['imageName'],
                marker=obj['marker'],  # TODO: What does this represent? Only on PlayerNDeadFigureM?
            )

        elif obj['_class_'].endswith('.ActorGroup'):
            for group in battle.players[0].groups + battle.players[1].groups:
                if not group.is_described():
                    group.name = obj['name']
                    group.set_archetype(' '.join([obj['race'], obj['characterClass']]))
                    break

        elif obj['_class_'].endswith('.ActorInstance'):
            for group in battle.players[0].groups + battle.players[1].groups:
                if not group.is_described():
                    group.figure = obj['depiction']
                    group.audio_key = obj['audioKey']
                    group.x = obj['location.x']
                    group.y = obj['location.y']
                    group.fx = obj['facing.x']
                    group.fy = obj['facing.y']
                    break

        else:
            print('Ignored:', obj)

    return battle


# Extract extension events
def extension_events(battle, extensions):
    events = []
    player_turn = -1
    must_discard = [-1, -1]
    for ex in extensions:
        ex_name = ex.get('_NAME')
        event_type = ex.get('type')

        if ex_name != 'battleTimer' and (ex_name != 'battle' or event_type == 'done'):
            continue

        if ex_name == 'battleTimer':
            player_index = ex['playerIndex']
            start = ex['start']
            remaining = ex['timeRemaining']

            if start:
                player_turn = player_index
                events.append(ExStartTimer(
                    -1,
                    player_index,
                    remaining,
                ))
                
            else:
                player_turn = -1
                events.append(ExPauseTimer(
                    -1,
                    player_index,
                    remaining,
                ))

        elif event_type == 'deckPeeksSent':
            events.append(ExDeckPeek(
                player_turn,
            ))

        elif event_type == 'handPeeksSent':
            events.append(ExHandPeek(
                player_turn,
            ))

        elif event_type == 'deckPeeks':
            # If user is still unknown, use this deckPeeks to determine who it is
            if battle.user is None:
                user = ex['SENDID'][0]
                battle.set_user(user)

            # For every card in the peeks array, extract its info and append an event for it
            deck_peeks = ex['DP']['peeks']
            for peek in deck_peeks:
                events.append(ExCardDraw(
                    player_turn,
                    player_index=peek['owner'],
                    group_index=peek['group'],
                    card_index=peek['card'],
                    original_player_index=peek['cownerp'],
                    original_group_index=peek['cownerg'],
                    item_name=peek['origin'],
                    card_name=peek['type'],
                ))

        elif event_type == 'handPeeks':
            # For every card in the peeks array, extract its info and append an event for it
            hand_peeks = ex['HP']['peeks']
            for peek in hand_peeks:
                events.append(ExCardReveal(
                    player_turn,
                    player_index=peek['owner'],
                    group_index=peek['group'],
                    card_index=peek['card'],
                    original_player_index=peek['cownerp'],
                    original_group_index=peek['cownerg'],
                    item_name=peek['origin'],
                    card_name=peek['type'],
                ))

        elif event_type == 'action':
            # For every card in the peeks array, extract its info and append an event for it
            hand_peeks = ex['HP']['peeks']
            for peek in hand_peeks:
                events.append(ExCardPlay(
                    player_turn,
                    player_index=peek['owner'],
                    group_index=peek['group'],
                    card_index=peek['card'],
                    original_player_index=peek['cownerp'],
                    original_group_index=peek['cownerg'],
                    item_name=peek['origin'],
                    card_name=peek['type'],
                ))

                if 'TARP' in ex:
                    events.append(ExSelectTarget(
                        player_turn,
                        target_player_indices=ex['TARP'],
                        target_group_indices=ex['TARG'],
                    ))

        elif event_type == 'selectCard':
            # Discard during round
            if 'HP' in ex:
                hand_peeks = ex['HP']['peeks']
                for peek in hand_peeks:
                    events.append(ExCardDiscard(
                        player_turn,
                        player_index=peek['owner'],
                        group_index=peek['group'],
                        card_index=peek['card'],
                        original_player_index=peek['cownerp'],
                        original_group_index=peek['cownerg'],
                        item_name=peek['origin'],
                        card_name=peek['type'],
                    ))

            # Discard at end of round
            else:
                player_index = must_discard[0]
                group_index = must_discard[1]
                card_index = ex['sel']

                try:
                    card = battle.players[player_index].groups[group_index].hand[card_index]
                except:
                    pass
                else:
                    events.append(ExCardDiscard(
                        player_turn,
                        player_index,
                        group_index,
                        card_index,
                        original_player_index=card.original_player_index,
                        original_group_index=card.original_group_index,
                        item_name=card.item_name,
                        card_name=card.card_name,
                    ))

        # elif event_type == 'selectCards':
        #     if 'SELP' in ex:
        #         selected_player_indices = ex['SELP']
        #         selected_group_indices = ex['SELG']
        #         selected_card_indices = ex['SELCC']
        #         for i in range(len(selected_player_indices)):
        #             events.append(ExSelectEvent(player_turn, selected_player_indices[i], selected_group_indices[i],
        #                                         selected_card_indices[i]))

        elif event_type == 'mustDiscard':
            player_index = ex['PUI']
            group_index = ex['ACTG']
            
            events.append(ExMustDiscard(
                player_turn,
                player_index,
                group_index,
            ))
            
            # Remember who must discard
            must_discard = [player_index, group_index]

        elif event_type == 'noMoreDiscards':
            events.append(ExNoDiscards(
                player_turn,
            ))

        elif event_type == 'hasTrait':
            events.append(ExMustTrait(
                player_turn,
                player_index=ex['PUI'],
            ))

        elif event_type == 'noMoreTraits':
            events.append(ExNoTraits(
                player_turn,
            ))

        elif event_type in ('triggerFail', 'triggerSucceed') and 'TCLOC' in ex:
            location = ex['TCLOC']
            
            if location == 0:
                events.append(ExTriggerInHand(
                    player_turn,
                    die_roll=ex['TROLL'],
                    required_roll=ex['TTHRESH'],
                    hard_to_block=ex['TPEN'],
                    easy_to_block=ex['TBON'],
                    player_index=ex['PUI'],
                    group_index=ex['ACTG'],
                    card_index=ex['ACTC'],
                ))

            elif location == 1:
                events.append(ExTriggerTrait(
                    player_turn,
                    die_roll=ex['TROLL'],
                    required_roll=ex['TTHRESH'],
                    hard_to_block=ex['TPEN'],
                    easy_to_block=ex['TBON'],
                    player_index=ex['PUI'],
                    group_index=ex['ACTG'],
                ))

            elif location == 2:
                events.append(ExTriggerTerrain(
                    player_turn,
                    die_roll=ex['TROLL'],
                    required_roll=ex['TTHRESH'],
                    hard_to_block=ex['TPEN'],
                    easy_to_block=ex['TBON'],
                    square=[ex['TARX'], ex['TARY']],
                ))

        elif event_type == 'target':
            events.append(ExSelectTarget(
                player_turn,
                target_player_indices=ex['TARP'],
                target_group_indices=ex['TARG'],
            ))

        elif event_type == 'selectSquare':
            events.append(ExSelectSquare(
                player_turn,
                square=[ex['TARX'], ex['TARY']],
                facing=[ex['TARFX'], ex['TARFY']],
            ))

        elif event_type == 'genRand':
            events.append(ExRNG(
                player_turn,
                rands=ex['RAND'],
            ))

        elif event_type == 'pass':
            events.append(ExPass(
                player_turn,
            ))

        elif event_type == 'forceLoss':
            events.append(ExResign(
                player_turn,
            ))

        else:
            print('Ignored:', ex)

    return events


# Extract message events
# TODO: Active Player = No Traits
def message_events(battle, messages):
    events = []

    p0 = re.escape(battle.players[0].name)
    p1 = re.escape(battle.players[1].name)
    player = '({}|{})'.format(p0, p1)
    p0g0 = re.escape(battle.players[0].groups[0].name)
    p0g1 = re.escape(battle.players[0].groups[1].name)
    p0g2 = re.escape(battle.players[0].groups[2].name)
    p1g0 = re.escape(battle.players[1].groups[0].name)
    p1g1 = re.escape(battle.players[1].groups[1].name)
    p1g2 = re.escape(battle.players[1].groups[2].name)
    group = '({}|{}|{}|{}|{}|{})'.format(p0g0, p0g1, p0g2, p1g0, p1g1, p1g2)

    start_round = re.compile(r'^Starting round (\d+)$')
    end_round = re.compile(r'^Turn Complete$')
    scoring_phase = re.compile(r'^Scoring Phase: initiated$')
    discard_phase = re.compile(r'^Discard Phase: initiated$')
    defeat = re.compile(r'^{} was defeated$'.format(player))
    draw = re.compile(r'^{} drew (.+) for {}$'.format(player, group))
    must_trait = re.compile(r'^{} must play a Trait$'.format(player))
    must_target = re.compile(r'^Participant {} must select targets$'.format(player))
    attach_trait = re.compile(r'^Attaching (.+) to {}$'.format(group))
    detach_trait = re.compile(r'^Detaching and discarding (.+) from {}$'.format(group))
    attach_terrain = re.compile(r'^Attaching (.+) to \((\d+), (\d+)\)$')
    active_player = re.compile(r'^The active player is now {}$'.format(player))
    passed = re.compile(r'^{} passed\.$'.format(player))
    ended_round = re.compile(r'^{} ended the round.$'.format(player))
    cancelling = re.compile(r'^Action: (.+) is invalid - cancelling$')
    cancelled = re.compile(r'^(.+) was cancelled.$')
    damage = re.compile(r'^{} took (\d+) damage$'.format(group))
    heal = re.compile(r'^{} healed (\d+)$'.format(group))
    die = re.compile(r'^{} died$'.format(group))
    block = re.compile(r'^{}, health = (\d+) \(pi:(\d), gi:(\d), ai:(\d)\)  blocks (.+)$'.format(group))
    autoselect = re.compile(r'^SeeverSelectCardsCommand:: selected card (.+)$')

    for m in messages:
        event = m.get('Event')
        msg = m.get('Msg')

        if event is not None:
            if event == 'StartGame':
                events.append(MsgStartGame())

            elif event == 'GameOver':
                events.append(MsgEndGame())

            elif event == 'Attachment Phase Initiated':
                events.append(MsgTraitPhase())

            elif event == 'Draw Phase Initiated':
                events.append(MsgDrawPhase())

            elif event == 'Action Phase Initiated':
                events.append(MsgActionPhase())

            elif event == 'PlayAction':
                targets = m['Targets']
                if targets == '':
                    targets = []
                elif isinstance(targets, str):
                    targets = [targets]
                
                events.append(MsgCardPlay(
                    group=m['Instigator'],
                    card=m['Action'],
                    targets=targets,
                ))

            elif event == 'Move':
                events.append(MsgMove(
                    player=m['Player'],
                    group=m['Actor'],
                    start=m['Origin'],
                    end=m['Destination'],
                    start_facing=m['StartFacing'],
                    end_facing=m['EndFacing'],
                ))

            elif event.startswith('Trigger'):
                loc = m['TriggerLocation']
                if loc == 'SquareAttachment':
                    msg = MsgTriggerTerrain
                elif loc == 'ActorAttachment':
                    msg = MsgTriggerTrait
                else:
                    msg = MsgTriggerInHand
                    
                events.append(msg(
                    group=m['TriggeringActor'],
                    card=m['Trigger'],
                    target=m['AffectedActors'],
                    success=event.endswith('Succeed'),
                    cause=m['TriggerType'],
                ))

            elif event == 'Needs to discard a card':
                events.append(MsgMustDiscard(
                    group=m['Group'],
                ))

            elif event == 'Discard':
                events.append(MsgDiscard(
                    group=m['Group'],
                    card=m['Card'],
                ))

            elif event == 'SelectCardRequired':
                player_id = m['PlayerID']
                choice_type = m['ChoiceType']  # TODO: What can this be?
                
                events.append(MsgMustSelect(
                    player=m['Participant'],
                    options=m['Selections'],
                ))

            elif event == 'SelectCard':
                events.append(MsgSelect(
                    player=m['Participant'],
                    card=m['Selection'],
                ))

            elif event == 'AttachmentExpired':
                loc = m['AttachedTo']
                if isinstance(loc, list):
                    msg = MsgDetachTerrain
                else:
                    msg = MsgDetachTrait
                    
                events.append(msg(
                    loc,
                    card=m['Attachment'],
                ))

            elif event == 'startTimer':
                events.append(MsgStartTimer(
                    player_index=m['PlayerIndex'],
                    remaining=m['Remaining'],
                ))

            elif event == 'stopTimer':
                events.append(MsgPauseTimer(
                    player_index=m['PlayerIndex'],
                    remaining=m['Remaining'],
                ))

            else:
                print('Ignored:', m)

        elif msg is not None:
            if start_round.fullmatch(msg):
                match = start_round.fullmatch(msg).groups()
                events.append(MsgStartRound(
                    game_round=int(match[0]),
                ))

            elif end_round.fullmatch(msg):
                events.append(MsgEndRound())

            elif scoring_phase.fullmatch(msg):
                events.append(MsgScoringPhase())

            elif discard_phase.fullmatch(msg):
                events.append(MsgDiscardPhase())

            elif defeat.fullmatch(msg):
                match = defeat.fullmatch(msg).groups()
                events.append(MsgDefeat(
                    player=match[0],
                ))

            elif draw.fullmatch(msg):
                match = draw.fullmatch(msg).groups()
                card = match[1]
                
                if card == 'a card':
                    events.append(MsgHiddenDraw(
                        player=match[0],
                        group=match[2],
                    ))
                    
                else:
                    events.append(MsgCardDraw(
                        player=match[0],
                        group=match[2],
                        card=match[1],
                    ))

            elif must_trait.fullmatch(msg):
                match = must_trait.fullmatch(msg).groups()
                events.append(MsgMustTrait(
                    player=match[0],
                ))

            elif must_target.fullmatch(msg):
                match = must_target.fullmatch(msg).groups()
                events.append(MsgMustTarget(
                    player=match[0],
                ))

            elif attach_trait.fullmatch(msg):
                match = attach_trait.fullmatch(msg).groups()
                events.append(MsgAttachTrait(
                    group=match[1],
                    card=match[0],
                ))

            elif detach_trait.fullmatch(msg):
                match = detach_trait.fullmatch(msg).groups()
                events.append(MsgDetachTrait(
                    group=match[1],
                    card=match[0],
                ))

            elif attach_terrain.fullmatch(msg):
                match = attach_terrain.fullmatch(msg).groups()
                events.append(MsgAttachTerrain(
                    square=[int(match[1]), int(match[2])],
                    card=match[0],
                ))

            elif active_player.fullmatch(msg):
                match = active_player.fullmatch(msg).groups()
                events.append(MsgPlayerTurn(
                    player=match[0],
                ))

            elif passed.fullmatch(msg):
                match = passed.fullmatch(msg).groups()
                events.append(MsgPass(
                    player=match[0],
                ))

            elif ended_round.fullmatch(msg):
                match = ended_round.fullmatch(msg).groups()
                events.append(MsgPass(
                    player=match[0],
                ))

            elif cancelling.fullmatch(msg):
                match = cancelling.fullmatch(msg).groups()
                events.append(MsgCancelAction(
                    card=match[0],
                ))

            elif cancelled.fullmatch(msg):
                match = cancelled.fullmatch(msg).groups()
                events.append(MsgStopCard(
                    card=match[0],
                ))

            elif damage.fullmatch(msg):
                match = damage.fullmatch(msg).groups()
                events.append(MsgDamage(
                    group=match[0],
                    hp=int(match[1]),
                ))

            elif heal.fullmatch(msg):
                match = heal.fullmatch(msg).groups()
                events.append(MsgHeal(
                    group=match[0],
                    hp=int(match[1]),
                ))

            elif die.fullmatch(msg):
                match = die.fullmatch(msg).groups()
                events.append(MsgDeath(
                    group=match[0],
                ))

            elif block.fullmatch(msg):
                match = block.fullmatch(msg).groups()
                player_index = int(match.groups()[2])
                group_index = int(match.groups()[3])
                
                events.append(MsgBlock(
                    player_index,
                    group_index,
                    card=match[5],
                ))
                
                events.append(MsgHealth(
                    player_index,
                    group_index,
                    hp=int(match[1]),
                ))

            elif autoselect.fullmatch(msg):
                match = autoselect.fullmatch(msg).groups()
                events.append(MsgAutoselect(
                    card=match[0],
                ))

            else:
                print('Ignored:', m)

        else:
            print('Ignored:', m)

    return events


# Form higher-level events
def refine_events(battle, ex_events, msg_events):
    # TODO

    for event in ex_events:
        pass
        print(event)

    for event in msg_events:
        pass
        # print(event)

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
        print('Failed to find joinbattle')
        return None, None

    # Parse battle logs
    extensions, messages = log_parse.parse_battle('\n'.join(log_lines[first_line_index:]))
    joinbattle, extensions = extensions[0], extensions[1:]

    # Load objects into battle
    battle = load_battle_objects(joinbattle['objects'])

    if not battle.is_described():
        pass  # Battle not completely started

    # Extract extension events
    ex_events = extension_events(battle, extensions)

    # Extract message events
    msg_events = message_events(battle, messages)

    # Interpolate and extrapolate to form higher-level events
    events = refine_events(battle, ex_events, msg_events)

    return events, battle
