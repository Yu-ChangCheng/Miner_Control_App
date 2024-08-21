from flask import Flask, jsonify, request # type: ignore
from datetime import datetime, timedelta

app = Flask(__name__) 

# Dictionary to store auth tokens with TTL
miner_ips = {}

# Dictionary to store curtail states and their tokens
miner_states = {}

# Dictionary to store miner profiles and their tokens
miner_profiles = {}


@app.route('/api/login', methods=['POST'])
def login():
    
    data = request.json
    miner_ip = data['miner_ip']
    
    # Check if miner_ip is already in the dictionary
    if miner_ip in miner_ips and miner_ips[miner_ip]['ttl'] > datetime.utcnow():
        return jsonify({'message': 'Miner already logged in.', 'token': miner_ips[miner_ip]['token']})

    token = miner_ip + '_token'
    
    # Set TTL to 1 minute from the current time
    expiration_time = datetime.utcnow() + timedelta(minutes=1)
    
    # Store the Token and TTL in the dictionary
    miner_ips[miner_ip] = {'token': token, 'ttl': expiration_time}
    
    return jsonify({'message': 'Miner logged in.', 'token': token, 'ttl': expiration_time})


@app.route('/api/logout', methods=['POST'])
def logout():
        
    data = request.json
    miner_ip = data['miner_ip']
    
    # Check if miner_ip is already in the dictionary
    if miner_ip in miner_ips:
        del miner_ips[miner_ip]
        return jsonify({'message': 'Miner logged out.'})
    
    return jsonify({'message': 'Miner not logged in.'})


@app.route('/api/curtail', methods=['POST'])
def curtail():
    
    data = request.json
    mode = data.get('mode')
    token = data.get('token')
    
    # Check if miner_ip is already in the dictionary
    if not any(entry['token'] == token and entry['ttl'] > datetime.utcnow() for entry in miner_ips.values()):
        return jsonify({'message': 'Unauthorized. Please login with a valid token.'}), 401

    # Check if mode is valid
    if mode not in ['active', 'sleep']:
        return jsonify({'message': 'Invalid curtail mode. Use active or sleep.'}), 400
    
    # Check if the miner is already in the requested state
    current_state = miner_states.get(token)
    if current_state == mode:
        return jsonify({'message': f'Miner is already in {mode} mode.'}), 400

    # update miner curtail state
    miner_states[token] = mode
    
    return jsonify({'message': f'Miner curtail state updated to {mode}.'})


@app.route('/api/profileset', methods=['POST'])
def profileset():
    
    data = request.json
    profile = data.get('profile')
    token = data.get('token')
    
    # check if miner_ip is already in the dictionary
    if not any(entry['token'] == token and entry['ttl'] > datetime.utcnow() for entry in miner_ips.values()):
        return jsonify({'message': 'Unauthorized. Please login with a valid token.'}), 401
    
    # Check if profile is valid
    if profile not in ['underclock', 'overclock', 'normal']:
        return jsonify({'message': 'Invalid profile. Use underclock, overclock or normal.'}), 400
    
    # check if miner is already in the requested profile
    current_profile = miner_profiles.get(token)
    if current_profile == profile:
        return jsonify({'message': f'Miner is already in {profile} profile.'}), 400
    
    # update miner profile
    miner_profiles[token] = profile
    
    return jsonify({'message': f'Miner profile updated to {profile}.'})


if __name__ == '__main__':
    app.run(debug=True)
