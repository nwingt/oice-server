import sqlalchemy as sa
from sqlalchemy.orm import relationship, validates
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import true, false
from modmod.models.base import (
    Base,
    BaseMixin,
)

from . import DBSession


class Macro(Base, BaseMixin):
    __tablename__ = 'macro'

    name = sa.Column(sa.Unicode(1024), nullable=False, server_default="")
    tagname = sa.Column(sa.Unicode(1024), nullable=False, server_default="")

    # The underlying MySQL Type used is "TEXT", which Mysql does not allow any native default values.
    # Any default value should be specified using `default` instead of `server_default`.
    content = sa.Column(sa.Text, nullable=True)

    attribute_definitions = relationship("AttributeDefinition",
                                         cascade="all,delete",
                                         order_by='AttributeDefinition.order',
                                         backref="macro",
                                         lazy="select")
    macro_type = sa.Column(sa.Unicode(1024), server_default='system')
    is_hidden = sa.Column(sa.Boolean, nullable=False, server_default=false())

    def serialize(self):
        return {
            'id': self.id,
            'name': self.tagname,
        }

    @validates('name')
    def validate_name(self, key, name):
        if not name:
            raise ValueError("Macro name is required.")
        else:
            return name

    @validates('tagname')
    def validate_tag(self, key, tagname):
        if not tagname:
            raise ValueError("Macro tagname is required.")
        else:
            return tagname


class MacroFactory(object):

    def __init__(self, request):
        self.request = request

    def __getitem__(self, key):
        macro = MacroQuery(DBSession).get_by_id(key)

        if not macro:
            raise NoResultFound('ERR_MACRO_NOT_FOUND')

        return macro


class MacroQuery:

    def __init__(self, session=DBSession):
        self.session = session

    def query(self):
        return self.session.query(Macro) \
                .filter(Macro.is_hidden == false())

    def get_by_id(self, macro_id):
        macro = self.session.query(Macro) \
                            .filter(Macro.id == macro_id) \
                            .one_or_none()
        return macro
