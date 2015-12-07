import wx, sys, os, logging, operator, traceback
from gettext import gettext as _
from squaremap import squaremap
from wx.lib.agw.ultimatelistctrl import UltimateListCtrl,ULC_REPORT,ULC_VIRTUAL,ULC_VRULES,ULC_SINGLE_SEL

if sys.platform == 'win32':
    windows = True
else:
    windows = False

log = logging.getLogger(__name__)

class ColumnDefinition(object):
    """Definition of a given column for display using attribute access"""

    index = None
    name = None
    attribute = None
    sortOn = None
    format = None
    defaultOrder = False
    percentPossible = False
    targetWidth = None
    getter = None
    
    sortDefault=False

    def __init__(self, **named):
        for key, value in named.items():
            setattr(self, key, value)
        if self.getter:
            self.get = self.getter 
        else:
            attribute = self.attribute 
            def getter( function ):
                return getattr( function, attribute, None )
            self.get = self.getter = getter

class DictColumn( ColumnDefinition ):
    def __init__(self, **named):
        for key, value in named.items():
            setattr(self, key, value)
        if self.getter:
            self.get = self.getter 
        else:
            attribute = self.attribute 
            def getter( function ):
                return function.get( attribute, None )
            self.get = self.getter = getter


class DataView(wx.ListCtrl):
    """A sortable profile list control"""

    indicated = -1
    total = 0
    percentageView = False
    activated_node = None
    selected_node = None
    indicated_node = None

    def __init__(
        self, parent,
        id=-1,
        pos=wx.DefaultPosition, size=wx.DefaultSize,
        style=wx.LC_REPORT|wx.LC_VIRTUAL|wx.LC_VRULES|wx.LC_SINGLE_SEL,
        validator=wx.DefaultValidator,
        columns=None,
        sortOrder=None,
        name=_("ProfileView"),
    ):
        wx.ListCtrl.__init__(self, parent, id, pos, size, style, validator,
                             name)

        if columns is not None:
            self.columns = columns

        if not sortOrder:
            sortOrder = [(x.defaultOrder,x) for x in self.columns if x.sortDefault]
        self.sortOrder = sortOrder or []
        self.sorted = []
        self.CreateControls()

    def SetPercentage(self, percent, total):
        """Set whether to display percentage values (and total for doing so)"""
        self.percentageView = percent
        self.total = total
        self.Refresh()

    def CreateControls(self):
        """Create our sub-controls"""
        wx.EVT_LIST_COL_CLICK(self, self.GetId(), self.OnReorder)
        wx.EVT_LIST_ITEM_SELECTED(self, self.GetId(), self.OnNodeSelected)
        wx.EVT_MOTION(self, self.OnMouseMove)
        wx.EVT_LIST_ITEM_ACTIVATED(self, self.GetId(), self.OnNodeActivated)
        self.CreateColumns()
    def CreateColumns( self ):
        """Create/recreate our column definitions from current self.columns"""
        self.SetItemCount(0)
        # clear any current columns...
        for i in range( self.GetColumnCount())[::-1]:
            self.DeleteColumn( i )
        # now create
        for i, column in enumerate(self.columns):
            column.index = i
            self.InsertColumn(i, column.name)
            if not windows or column.targetWidth is None:
                self.SetColumnWidth(i, wx.LIST_AUTOSIZE)
            else:
                self.SetColumnWidth(i, column.targetWidth)
    def SetColumns( self, columns, sortOrder=None ):
        """Set columns to a set of values other than the originals and recreates column controls"""
        self.columns = columns 
        self.sortOrder = [(x.defaultOrder,x) for x in self.columns if x.sortDefault]
        self.CreateColumns()

    def OnNodeActivated(self, event):
        """We have double-clicked for hit enter on a node refocus squaremap to this node"""
        try:
            node = self.sorted[event.GetIndex()]
        except IndexError, err:
            log.warn(_('Invalid index in node activated: %(index)s'),
                     index=event.GetIndex())
        else:
            wx.PostEvent(
                self,
                squaremap.SquareActivationEvent(node=node, point=None,
                                                map=None)
            )

    def OnNodeSelected(self, event):
        """We have selected a node with the list control, tell the world"""
        try:
            node = self.sorted[event.GetIndex()]
        except IndexError, err:
            log.warn(_('Invalid index in node selected: %(index)s'),
                     index=event.GetIndex())
        else:
            if node is not self.selected_node:
                wx.PostEvent(
                    self,
                    squaremap.SquareSelectionEvent(node=node, point=None,
                                                   map=None)
                )

    def OnMouseMove(self, event):
        point = event.GetPosition()
        item, where = self.HitTest(point)
        if item > -1:
            try:
                node = self.sorted[item]
            except IndexError, err:
                log.warn(_('Invalid index in mouse move: %(index)s'),
                         index=event.GetIndex())
            else:
                wx.PostEvent(
                    self,
                    squaremap.SquareHighlightEvent(node=node, point=point,
                                                   map=None)
                )

    def SetIndicated(self, node):
        """Set this node to indicated status"""
        self.indicated_node = node
        self.indicated = self.NodeToIndex(node)
        self.Refresh(False)
        return self.indicated

    def SetSelected(self, node):
        """Set our selected node"""
        self.selected_node = node
        index = self.NodeToIndex(node)
        if index != -1:
            self.Focus(index)
            self.Select(index, True)
        return index

    def NodeToIndex(self, node):
        for i, n in enumerate(self.sorted):
            if n is node:
                return i
        return -1

    def columnByAttribute(self, name):
        for column in self.columns:
            if column.attribute == name:
                return column
        return None

    def OnReorder(self, event):
        """Given a request to reorder, tell us to reorder"""
        column = self.columns[event.GetColumn()]
        return self.ReorderByColumn( column )

    def ReorderByColumn( self, column ):
        """Reorder the set of records by column"""
        # TODO: store current selection and re-select after sorting...
        single_column = self.SetNewOrder( column )
        self.reorder( single_column = True )
        self.Refresh()

    def SetNewOrder( self, column ):
        """Set new sorting order based on column, return whether a simple single-column (True) or multiple (False)"""
        if column.sortOn:
            # multiple sorts for the click...
            columns = [self.columnByAttribute(attr) for attr in column.sortOn]
            diff = [(a, b) for a, b in zip(self.sortOrder, columns)
                    if b is not a[1]]
            if not diff:
                self.sortOrder[0] = (not self.sortOrder[0][0], column)
            else:
                self.sortOrder = [
                    (c.defaultOrder, c) for c in columns
                ] + [(a, b) for (a, b) in self.sortOrder if b not in columns]
            return False
        else:
            if column is self.sortOrder[0][1]:
                # reverse current major order
                self.sortOrder[0] = (not self.sortOrder[0][0], column)
            else:
                self.sortOrder = [(column.defaultOrder, column)] + [
                    (a, b)
                    for (a, b) in self.sortOrder if b is not column
                ]
            return True

    def reorder(self, single_column=False):
        """Force a reorder of the displayed items"""
        if single_column:
            columns = self.sortOrder[:1]
        else:
            columns = self.sortOrder
        for ascending,column in columns[::-1]:
            # Python 2.2+ guarantees stable sort, so sort by each column in reverse 
            # order will order by the assigned columns 
            self.sorted.sort( key=column.get, reverse=(not ascending))

    def integrateRecords(self, functions):
        """Integrate records from the loader"""
        self.SetItemCount(len(functions))
        self.sorted = functions[:]
        self.reorder()
        self.Refresh()

    indicated_attribute = wx.ListItemAttr()
    indicated_attribute.SetBackgroundColour('#00ff00')

    def OnGetItemAttr(self, item):
        """Retrieve ListItemAttr for the given item (index)"""
        if self.indicated > -1 and item == self.indicated:
            return self.indicated_attribute
        return None

    def OnGetItemText(self, item, col):
        """Retrieve text for the item and column respectively"""
        # TODO: need to format for rjust and the like...
        try:
            column = self.columns[col]
            value = column.get(self.sorted[item])
        except IndexError, err:
            return None
        else:
            if value is None:
                return u''
            if column.percentPossible and self.percentageView and self.total:
                value = value / float(self.total) * 100.00
            if column.format:
                try:
                    return column.format % (value,)
                except Exception, err:
                    log.warn('Column %s could not format %r value: %r',
                        column.name, type(value), value
                    )
                    value = column.get(self.sorted[item] )
                    if isinstance(value,(unicode,str)):
                        return value
                    return unicode(value)
            else:
                if isinstance(value,(unicode,str)):
                    return value
                return unicode(value)

    def OnGetItemToolTip(self, item, col):
        return self.OnGetItemText(item, col) # XXX: do something nicer

    def SaveState( self, config_parser ):
        section = 'listctrl-%s'%(self.GetName())
        if not config_parser.has_section(section):
            config_parser.add_section(section)
        for i, dfn in enumerate(self.columns):
            col = self.GetColumn(i)
            config_parser.set( section, '%s_width'%dfn.attribute, str(col.GetWidth()) )
    def LoadState( self, config_parser ):
        section = 'listctrl-%s'%(self.GetName())
        if config_parser.has_section(section):
            for i, dfn in enumerate(self.columns):
                width = '%s_width'%dfn.attribute
                if config_parser.has_option(section, width):
                    try:
                        value = int(config_parser.get(section, width))
                    except ValueError:
                        log.warn( "Unable to restore %s %s", section, width )
                    else:
                        self.SetColumnWidth(i,value)
