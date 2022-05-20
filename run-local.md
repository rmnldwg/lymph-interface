# Run the interface locally

To use this interface on your machine, you can follow these steps below to get it up and running locally on your computer.


## Cloning the repo

Start by cloning this GitHub repository to you machine. In a terminal enter:

```shell
git clone https://github.com/rmnldwg/lymph-interface.git
```

and provide your credentials when prompted. Afterwards, ``cd`` into ``lymph-interface``.


## Set up environment

When working with python, it is always recommended to set up a virtual environment. You can create virtual environments in many different ways, but here we are going to use [``venv``](https://docs.python.org/3/library/venv.html), which is pretty simple to use and the recommended tool, according to the Python documentation.

``venv`` comes with a Python installation, which I assume you have. So create a blank virtual environment, use this command:

```shell
python3 -m venv yournewenvironment
```

where you can replace ``yournewenvironment`` with the name you want to give to your new environment. A common choice is ``.venv``, since it's short and the created directory is "hidden" (not really hidden, but it doesn't show up when you type ``ls``).

Then, depending on your operating system and used shell, you can activate the environment by typing

| Platform | shell           | command to activate                     |
| :------- | :-------------- | :-------------------------------------- |
| POSIX    | bash / zsh      | ``$ source <venv>/bin/activate``        |
|          | fish            | ``$ source <venv>/bin/activate.fish``   |
|          | csh / tcsh      | ``$ source <venv>/bin/activate.csh``    |
|          | PowerShell Core | ``$ source <venv>/bin/Activate.ps1``    |
| Windows  | cmd.exe         | ``C:\> <venv>\Scripts\activate.bat``    |
|          | cmd.exe         | ``PS C:\> <venv>\Scripts\Activate.ps1`` |

where ``<venv>`` should be replaced by the name you have given your virtual environment.

If everythin went according to plan, your terminal should now prefix everything with the name of the environment in brackets. E.g. on Ubuntu with bash the terminal now looks like this:

```shell
(.venv) user@machine:~$
```


## Installing prerequisites

In order to start the interface's server, you need to have [django](https://www.djangoproject.com/) along with several other prerequisites installed. The repository comes with a ``requirements.txt`` file, which one can use to install everything that is necessary. While inside the ``lymph-interface`` folder and with your virtual environment activated, type

```shell
pip install -r requirements.txt
```


## Adding a `settings.py` file

Usually, every django project has a `settings.py` file where all the project's settings live. E.g. security relevant options, which apps and plug-ins are used and so on. Since we wanted to be able to deploy multiple different version of the interface, we changed the approach to the settings slightly: There exists a `defaults.py` file that contains all default settings for the interface, which can then be modified using a custom (and untracked) `settings.py`. So, to use the interface, just simply create a `settings.py` containing one line of code:

```python
from .defaults import *
```

After that line you can change or add any setting you wish.


## Running the interface

Now you should be ready to execute the following commands:

```shell
python manage.py makemigrations patients accounts
python manage.py migrate
```

This will prepare django's database. If that worked, it is finally time to launch the server locally:

```shell
python manage.py runserver
```

If everything goes according to plan, django will ouput a link to the locally hosted web server. It usually runs at [http://127.0.0.1:8000/](http://127.0.0.1:8000/).


## Populating the database

Since uploading data (also to the local host) requires an authentication, you will want to create a superuser by running

```shell
python manage.oy createsuperuser
```

Afterwards you can use the defined credentials to log into the admin page at [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin) and edit all database entries.
