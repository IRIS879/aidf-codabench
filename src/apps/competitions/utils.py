'''
This file contains utilities for competitions
'''

from competitions.models import Competition


def get_popular_competitions(limit=4):
    """
    Function to return most popular competitions based on the amount of participants.

    :param limit: Amount of competitions to return. Default is 3.
    :rtype: list
    :return:  Most popular competitions.
    """

    competitions = Competition.objects.filter(published=True) \
        .order_by('-is_featured', '-participants_count')

    if len(competitions) <= limit:
        return competitions

    return competitions[:limit]


def get_recent_competitions(exclude_comps=None, limit=8):
    """
    Function to return recent competitions, excluding given competitions.

    :param limit: Amount of competitions to return. Default is 8.
    :param exclude_comps: A queryset or list of competitions to exclude.
    :rtype: list
    :return: List of recent competitions.
    """
    exclude_ids = [comp.id for comp in exclude_comps] if exclude_comps else []
    competitions = Competition.objects.filter(published=True) \
        .exclude(id__in=exclude_ids) \
        .order_by('-created_when')

    if len(competitions) <= limit:
        return competitions

    return competitions[:limit]
