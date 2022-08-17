from setuptools import setup

setup(
    name='access_point',
    version='0.1',
    description='Access Point service works as an interface for both Publisher and subscriber users. Translates redis-streams msgs to HTTP websockets messages.',
    author='Tarek Zaarour',
    author_email='tarek.zaarour@insight-centre.org',
    packages=['access_point'],
    zip_safe=False
)
