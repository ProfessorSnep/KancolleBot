"""Handles information about ships."""
import os
import userinfo
import json
import urllib.request
from io import BytesIO
from PIL import Image
from settings import setting

DIR_PATH = os.path.dirname(os.path.realpath(__file__))

_json_cache = {}


def read_json(filepath):
    """Return the JSON inside of the given JSON file."""
    if (filepath in _json_cache):
        return _json_cache[filepath]
    with open(filepath, 'r', encoding='utf-8') as fileinfo:
        data = json.load(fileinfo)
        _json_cache[filepath] = data
        return data


SHIP_DATA_FILE = os.path.join(DIR_PATH, "../ships.json")
SHIP_DATA = read_json(SHIP_DATA_FILE)

TYPE_DATA_FILE = os.path.join(DIR_PATH, "../types.json")

SEASONAL_DATA_FILE = os.path.join(DIR_PATH, "../seasonal.json")
SEASONAL_DATA = read_json(SEASONAL_DATA_FILE)

EXPERIENCE_DATA_FILE = os.path.join(DIR_PATH, "../experience.json")
EXPERIENCE_DATA = read_json(EXPERIENCE_DATA_FILE)

_sbase_cache = {}


class ShipBase:
    """The base type of a ship, including its shared information."""

    def __init__(self, sid, data):
        """Initialize the ship base.

        Parameters
        ----------
        sid : int
            The ship ID of the ship
        data : dict
            The JSON data of the specified ship
        """
        self.sid = sid
        self.kc3id = data['kc3id']
        self.name = data['name']
        self.class_name = data['class_name']
        self.rarity = data['rarity']
        self.stype = data['stype']
        self.quotes = data['quotes']
        self.remodels_from = data['remodels_from']
        self.remodels_into = data['remodels_into']
        self.remodel_level = data['remodel_level']
        self.images = data['images']
        self.can_drop = data['can_drop']
        self.can_craft = data['can_craft']

    @staticmethod
    def instance(shipid):
        """Get an instance of ShipBase for the given ship id."""
        if (shipid in _sbase_cache):
            return _sbase_cache[shipid]

        data = SHIP_DATA[str(shipid)]
        ins = ShipBase(shipid, data)
        _sbase_cache[shipid] = ins
        return ins

    def get_quote(self, key):
        """Return a quote that the ship has, given its key."""
        if (key in self.quotes):
            return self.quotes[key]
        try:
            ship = self
            while (ship.remodels_from):
                ship = ShipBase.instance(ship.remodels_from)
                quo = ship.get_quote(key)
                if (quo):
                    return quo
        except TypeError:
            pass
        return "???"

    def get_first_base(self):
        """Get the original base of this ship, before all remodels."""
        ship = self
        try:
            while (ship.remodels_from):
                ship = ShipBase.instance(ship.remodels_from)
        except TypeError:
            pass
        return ship

    def has_seasonal_cg(self):
        """Return True if the ship has a seasonal artwork."""
        return str(self.sid) in SEASONAL_DATA

    def get_cg(self, ico=False, dmg=False):
        """Return the full CG of the ship.

        Parameters
        ----------
        ico : bool
            True if requesting the icon, False if requesting the full CG.
        dmg : bool
            True if requesting the damaged version, False if normal version.

        Returns
        -------
        PIL.Image
            The CG requested, in its native size
        """
        seasonal = self.has_seasonal_cg()
        file_dir = "../seasonal_cg/" if seasonal else ("../icos/" if
                                                       ico else "../cgs/")
        file_dir = os.path.join(DIR_PATH, file_dir)
        info_name = 'small' if ico else 'full'
        info_name += '_damaged' if dmg else ''
        image_info = (SEASONAL_DATA[str(self.sid)]['images'][info_name] if
                      seasonal else self.images[info_name])

        try:
            img = Image.open(file_dir + image_info['file_name'])
            return img
        except IOError:
            url = image_info['url']
            req = urllib.request.urlopen(url)
            imgdata = Image.open(BytesIO(req.read())).convert('RGBA')
            imgdata.save(file_dir + image_info['file_name'])
            return imgdata


class ShipInstance:
    """Represents an instance of a ship in a user's inventory."""

    def __init__(self, invid, sid, owner, level=1, exp=0):
        """Initialize the ship instance.

        Parameters
        ----------
        invid : int
            The inventory slot this ship takes up.
        sid : int
            The ship id of the ship.
        owner : int
            The discord id of the owner of this ship.
        level : int
            The ship's level.
        exp : int
            The ship's current exp.
        """
        self.invid = invid
        self.sid = sid
        self.owner = owner
        self.level = level
        self.exp = exp

    def base(self):
        """Return the ShipBase corresponding to this ship."""
        return ShipBase.instance(self.sid)

    @staticmethod
    def new(sid, owner):
        """Make a new ship with the given shipid owned by the given owner."""
        return ShipInstance(-1, sid, owner)

    def add_exp(self, exp):
        """Add EXP to the local copy of the ship.

        Returns
        -------
        bool
            Whether or not the ship levelled up in the process.
        """
        if (not setting('features.levels_enabled')):
            return None
        req = self.exp_req()
        self.exp += exp
        lvl = False
        if (self.level != setting('levels.level_cap') and self.level < setting('levels.level_cap_married')):
            if (self.exp > req):
                self.level += 1
                self.exp -= req
                lvl = True
                self.add_exp(0)  # level up as much as possible
        else:
            self.exp = 0
        userinfo.update_ship_exp(self)
        return lvl

    def exp_req(self):
        """Get the amount of EXP required for the next level."""
        lvl = min(setting('levels.level_cap_married'), max(1, self.level))
        return EXPERIENCE_DATA['exp'][str(lvl)]

    def is_remodel_ready(self):
        """Return true if the ship's level is high enough for a remodel."""
        base = self.base()
        if (not base.remodels_into):
            return False
        return self.level >= base.remodel_level


def get_rarity_backdrop(rarity):
    """Return an image of the corresponding rarity background.

    Returns
    -------
    PIL.Image
        The image resized to the given size.
    """
    rarity -= 1
    rimg = Image.open(DIR_PATH + '/images/bg_%d.png' % (rarity))
    return rimg


ALL_SHIP_TYPES = []


class ShipType:
    """Type or class of a ship."""

    def __init__(self, discriminator, full_name, resource_mult):
        """Initialize the ship type.

        Parameters
        ----------
        discriminator : str
            The shorthand discriminator for the ship type.
        full_name : str
            The full type name.
        resource_mult : float
            A multiplier for the amount of resources this ship type takes
            compared to others.
        """
        self.discriminator = discriminator
        self.full_name = full_name
        self.resource_mult = resource_mult
        ALL_SHIP_TYPES.append(self)

    def __str__(self):
        """Return the full name of the ship."""
        return self.full_name


type_data = read_json(TYPE_DATA_FILE)
for k, v in type_data.items():
    ShipType(k, v['name'], v['resource_mult'])


def get_ship_type(discrim):
    """Return the ShipType object corresponding to the given discriminator."""
    r = [x for x in ALL_SHIP_TYPES if x.discriminator == discrim]
    if len(r) > 0:
        return r[0]
    return None


def get_all_ships(allow_remodel=True, only_droppable=False,
                  only_craftable=False, type_discrims=None):
    """Return every ship base.

    Parameters
    ----------
    allow_remodel : bool
        If False, only return ships with no past remodels.
    only_droppable : bool
        If True, only return ships that are able to be dropped.
    only_craftable : bool
        If True, only return ships that can be crafted.
    type_discrims : list
        A list (str) of discriminators of ship types,
        if not None, only returns ships of the given types.
    """
    ret = []

    for sid in SHIP_DATA.keys():
        ins = ShipBase.instance(sid)
        if (only_droppable and not ins.can_drop):
            continue
        if (only_craftable and not ins.can_craft):
            continue
        if (ins.remodels_from and not allow_remodel):
            continue
        if (type_discrims and ins.stype not in type_discrims):
            continue
        ret.append(ins)

    return ret
