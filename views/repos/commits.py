#!/usr/local/bin/python2.7
#coding:utf-8

import logging
from datetime import datetime

from flask import request, abort

from utils.local import reqcache

import config
from libs.code import render_diff
from utils.jagare import get_jagare
from utils.avatar import get_avatar
from utils.helper import MethodView, Obj
from utils.formatter import format_time
from utils.account import login_required
from utils.organization import member_required
from utils.repos import repo_required, get_branches, \
        render_commits_page, get_url, parse_raw_diff_patches

from query.account import get_user_from_alias

logger = logging.getLogger(__name__)

class Commits(MethodView):
    decorators = [repo_required(), member_required(admin=False), login_required('account.login')]
    def get(self, organization, member, repo, admin, team, team_member, version=None, path=None):
        page = request.args.get('p', 1)
        try:
            page = int(page)
        except ValueError:
            raise abort(403)
        version = version or repo.default

        jagare = get_jagare(repo.id, repo.parent)
        error, commits = jagare.get_log(
                repo.get_real_path(), page=page, \
                size=config.COMMITS_PER_PAGE, shortstat=1, \
                start=version, path=path, \
        )
        if not commits:
            raise abort(404)

        list_page = render_commits_page(repo, page, path)
        commits = self.render_commits(jagare, organization, repo, commits, list_page, path=path)
        return self.render_template(
                    member=member, repo=repo, \
                    organization=organization, \
                    branches=get_branches(repo, jagare), \
                    error=error, \
                    version=version, \
                    admin=admin, team=team, team_member=team_member, \
                    commits=commits, \
                    path=path, \
                    list_page=list_page, \
                )

    def render_commits(self, jagare, organization, repo, commits, list_page, path):
        pre = None
        for commit in commits:
            render_commit(commit, organization, repo)
            commit['view'] = get_url(organization, repo, version=commit['sha'], path=path)
            if not pre:
                pre = commit
            else:
                commit['pre'] = pre
                pre = commit
            yield commit

class Commit(MethodView):
    decorators = [repo_required(), member_required(admin=False), login_required('account.login')]
    def get(self, organization, member, repo, admin, team, team_member, version):
        jagare = get_jagare(repo.id, repo.parent)
        error, commits = jagare.get_log(
                repo.get_real_path(), \
                size=1, start=version, \
        )
        if not commits:
            raise abort(404)
        commit = commits[0]
        render_commit(commit, organization, repo)
        commit['diffs'] = split_diff(commit['diff'])
        return self.render_template(
                    member=member, repo=repo, \
                    organization=organization, \
                    admin=admin, team=team, team_member=team_member, \
                    commit=commit, \
                )

def render_commit(commit, organization, repo):
    commit['author_date'] = datetime.fromtimestamp(float(commit['author_time'])).date()
    commit['author_time'] = format_time(commit['author_time'])
    author = reqcache.get(commit['author_email'])
    if not author:
        author = get_user_from_alias(commit['author_email'])
        reqcache.set(commit['author_email'], author)
    if not author:
        author = Obj()
        author.email = commit['author_email']
        author.name = None
        author.avatar = lambda size:get_avatar(author.email, size)
    commit['author'] = author

def split_diff(diff):
    ds = parse_raw_diff_patches(diff)
    for d in ds:
        d['diff'] = render_diff('\n'.join(d['diff']))
        yield d

