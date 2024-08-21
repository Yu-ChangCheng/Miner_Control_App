
# MinerControlApp

This repository contains the `MinerControlApp`, a Python application designed to manage the operation of a fleet of miners based on the time of day. The application interfaces with a Miner Control API to log in to miners, set their operational modes, and log out.

## Features

- **Dynamic Mode Control:** Automatically adjusts miner profiles (e.g., overclock, normal, underclock) and curtailment modes (active or sleep) based on the time of day.
- **Concurrent Processing:** Handles multiple miners simultaneously using a thread pool, improving efficiency.
- **Robust Error Handling:** Implements retry logic with exponential backoff and specific error handling, including unauthorized token handling and ignoring certain predefined errors.
- **Logging:** Logs all significant operations and errors to a log file for easy debugging and monitoring.

## Video Walk Through
[Youtube Video](https://youtu.be/rvQJKnbbFNc)

## Requirements

- Python 3.6+
- `requests` library for making HTTP requests.
- `Flask` For server.
- `unittest2` For testing.
- `coverage` For testing.

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Yu-ChangCheng/MinerControlApp.git
   cd MinerControlApp
   ```

2. **Install required Python packages:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the server:**

   ```bash
   python app.py
   ```

In the other terminal run

4. **Run the application:**

   ```bash
   python miner_control_app.py
   ```

## Configuration

- **Miner IPs:** The list of miner IPs is specified in the `miner_ips` list within the `__main__` block of `miner_control_app.py`. Replace the sample IPs with actual miner IPs.
  
- **Logging:** The application logs its operations to `miner_control.log` by default. You can change the log file name by passing a different value to the `log_file` parameter in the `MinerControlApp` constructor.

## Usage

The application automatically determines the appropriate operational mode based on the time of day:

- **00:00 - 06:00:** Overclock, active
- **06:00 - 12:00:** Normal, active
- **12:00 - 18:00:** Underclock, active
- **18:00 - 00:00:** Normal, sleep

The app continuously cycles through these time intervals, processing all miners accordingly.

## Testing

This project includes a comprehensive set of unit tests to validate the functionality of the `MinerControlApp`. The tests simulate interactions with the Miner Control API, including successful and failed login attempts, setting profiles, and handling curtailment modes.

### Running Tests

1. **Run the tests:**

   ```bash
   python -m unittest discover -s tests
   ```
   
   OR 

   If you want to see the coverage report

   ```bash
   coverage run -m unittest discover -v 
   coverage report -m 
   ```


2. **Test Files:**

   - `test_miner_control_app.py`: Contains unit tests for the main functionalities of the `MinerControlApp`.

## Logging

- All significant operations and errors are logged to `miner_control.log` with timestamps and log levels.
- Log messages include the success and failure of API requests, token handling, and the results of each operational cycle.

## Contribution

Contributions to this project are welcome. Please submit a pull request with a detailed description of your changes.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.

---

For any additional questions or help, please feel free to contact [ycheng345@gatech.edu].

---
