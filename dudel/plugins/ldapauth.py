from dudel import app, db
from dudel.login import login_provider
import ldap

config = app.config["LDAP"]

class LdapConnector(object):
    def __init__(self):
        self.connected = False
        self.bound = False

    def connect(self):
        if self.connected: return
        self.connection = ldap.initialize(config["HOST"])
        self.connected = True

    def bind_global(self):
        self.bind(config["GLOBAL"]["BIND_DN"], config["GLOBAL"]["PASSWORD"])

    def bind(self, dn, password):
        if self.bound:
            self.disconnect()
        self.connect()
        self.connection.simple_bind_s(dn, password)
        self.bound = True

    def disconnect(self):
        self.connected = False
        self.bound = False

    def update(self):
        self.update_users()
        self.update_groups()

    def get_users(self):
        self.bind_global()
        results = self.connection.search_s(config["USERS"]["DN"], ldap.SCOPE_SUBTREE)

        groups = {}

        for dn, data in results:
            name = data[config["GROUPS"]["ATTRIBUTES"]["NAME"]][0]
            identifier = data[config["GROUPS"]["ATTRIBUTES"]["IDENTIFIER"]][0]
            members = []
            if config["GROUPS"]["ATTRIBUTES"]["MEMBERS"] in data:
                members = data[config["GROUPS"]["ATTRIBUTES"]["MEMBERS"]]

            groups[identifier] = (identifier, name, members)

        return groups

    def update_users(self):
        users = self.get_users()

        for username, data in users.items():
            from dudel.models.user import User
            user = User.query.filter_by(username=username).first()
            if not user:
                user = User()
                user.username = username
                user.source = "ldap"
                db.session.add(user)
                self._update_user(user, data)
            elif user.source == "ldap":
                self._update_user(user, data)
            else:
                print("Will not update user %s, since it is not a LDAP user." % username)
        db.session.commit()

    def get_groups(self):
        self.bind_global()
        results = self.connection.search_s(config["GROUPS"]["DN"], ldap.SCOPE_SUBTREE, config["GROUPS"]["FILTER"])

        groups = {}

        for dn, data in results:
            name = data[config["GROUPS"]["ATTRIBUTES"]["name"]][0]
            identifier = data[config["GROUPS"]["ATTRIBUTES"]["identifier"]][0]
            members = []
            if config["GROUPS"]["ATTRIBUTES"]["members"] in data:
                members = data[config["GROUPS"]["ATTRIBUTES"]["members"]]

            groups[identifier] = (identifier, name, members)

        return groups

    def update_groups(self):
        groups = self.get_groups()

        for identifier, data in groups.items():
            from dudel.models.group import Group
            group = Group.query.filter_by(identifier=identifier).first()
            if not group:
                group = Group()
                group.source = "ldap"
                db.session.add(group)
                self._update_group(group, data)
            elif group.source == "ldap":
                self._update_group(group, data)
            else:
                print("Will not update group %s, since it is not a LDAP group." % identifier)
        db.session.commit()

    def _update_group(self, group, data):
        group.identifier = data[0]
        group.name = data[1]

        # Add new members
        for uid in data[2]:
            from dudel.models.user import User
            user = User.query.filter_by(username=uid).first()

            # Check if this user has not yet logged in, ignore them,
            # since the groups will be updated once they log in the
            # first time.
            if not user: continue

            if not user in group.users:
                group.users.append(user)

        # Remove members not in the group anymore
        users = []
        for user in group.users:
            if user.username in data[2]:
                users.append(user)
        group.users = users

    def try_login(self, username, password):
        escaped_username = ldap.dn.escape_dn_chars(username)

        try:
            self.connect()
            bind_dn = config["LOGIN"]["BIND_DN"].format(username=escaped_username)
            self.bind(bind_dn, password)

        except ldap.INVALID_CREDENTIALS:
            return False
        except ldap.LDAPError, e:
            return "LDAP Error while logging in: " + str(e)

        try:
            data_dn = config["LOGIN"]["DATA_DN"].format(username=escaped_username)
            results = self.connection.search_s(data_dn, ldap.SCOPE_SUBTREE)
            results = {k:(v if len(v)>1 else v[0]) for k,v in results[0][1].iteritems()}
            self.connection.unbind_s()
        except ldap.LDAPError, e:
            return "LDAP Error while getting User data: " + str(e)


        # At this point, the login was successful and we have data about the user
        from dudel.models.user import User
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User()
            user.username = username
            user.source = "ldap"
            db.session.add(user)

        self._update_user(user, results)
        self.update_groups()
        return user

    def _update_user(self, user, data):
        attrs = config["USERS"]["ATTRIBUTES"]
        for attr in ("username", "firstname", "_displayname", "lastname", "email"):
            if attr in attrs:
                setattr(user, attr, data[attrs[attr]])


ldap_connector = LdapConnector()

@login_provider("ldap")
def try_login_ldap(username, password):
    return ldap_connector.try_login(username, password)
