# Freifunk Potsdam Node Monitor

This is the website behind [the access point database of Potsdam][apmap].

## Development

You need [Python 3], [Git] and [Mongo-DB]. 

1. Clone the repository.
    ```sh
    git clone https://github.com/seth0r/ffp-monitor.git
    cd ffp-monitor
    ```
2. Create a virtual environment.
    ```sh
    pip install virtualenv
    virtualenv -p python3 ENV
    source ENV/bin/activate
    pip install -r requirements.txt
    ```

[apmap]: https://monitor.freifunk-potsdam.de

