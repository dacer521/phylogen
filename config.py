"""Simple configuration for the Phylogen app."""
import os


class Config:
    SECRET_KEY = os.environ.get('PHYLOGEN_SECRET', 'dev')

