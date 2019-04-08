"""Base class for objects of type source."""
from warnings import warn
import logging
import numpy as np
from scipy.spatial.distance import cdist

from vispy import scene
from vispy.scene import visuals
import vispy.visuals.transforms as vist

# from ._projection import _project_sources_data
# from .roi_obj import RoiObj
from ..utils.vispy_utils import (color2vb, normalize, vispy_array,
                                 wrap_properties, array2colormap)


logger = logging.getLogger('visbrain')
PROJ_STR = "%i sources visibles and not masked used for the %s"


class SourceObj():
    """Create a source object.

    Parameters
    ----------
    name : string
        Name of the source object.
    xyz : array_like
        Array of positions of shape (n_sources, 2) or (n_sources, 3).
    data : array_like | None
        Array of weights of shape (n_sources,).
    color : array_like/string/tuple | 'red'
        Marker's color. Use a string (i.e 'green') to use the same color across
        markers or a list of colors of length n_sources to use different colors
        for markers.
    alpha : float | 1.
        Transparency level.
    symbol : string | 'disc'
        Symbol to use for sources. Allowed style strings are: disc, arrow,
        ring, clobber, square, diamond, vbar, hbar, cross, tailed_arrow, x,
        triangle_up, triangle_down, and star.
    radius_min / radius_max : float | 5.0/10.0
        Define the minimum and maximum source's possible radius. By default
        if all sources have the same value, the radius will be radius_min.
    edge_color : string/list/array_like | 'black'
        Edge color of source's markers.
    edge_width : float | 0.
        Edge width source's markers.
    system : {'mni', 'tal'}
        Specify if the coodinates are in the MNI space ('mni') or Talairach
        ('tal').
    mask : array_like | None
        Array of boolean values to specify masked sources. For example, if data
        are p-values, mask could be non-significant sources.
    mask_color : array_like/tuple/string | 'gray'
        Color to use for masked sources.
    text : list | None
        Text to attach to each source. For example, text could be the name of
        each source.
    text_size : float | 2.
        Text size attached to sources.
    text_color : array_like/string/tuple | 'white'
        Text color attached to sources.
    text_bold : bool | False
        Specify if the text attached to sources should be bold.
    text_translate : tuple | (0., 2., 0.)
        Translate the text along the (x, y, z) axis.
    visible : bool/array_like | True
        Specify which source's have to be displayed. If visible is True, all
        sources are displayed, False all sources are hiden. Alternatively, use
        an array of shape (n_sources,) to select which sources to display.
    transform : VisPy.visuals.transforms | None
        VisPy transformation to set to the parent node.
    parent : VisPy.parent | None
        Markers object parent.
    verbose : string
        Verbosity level.
    _z : float | 10.
        In case of (n_sources, 2) use _z to specify the elevation.
    kw : dict | {}
        Optional arguments are used to control the colorbar
        (See :class:`ColorbarObj`).

    Notes
    -----
    List of supported shortcuts :

        * **s** : save the figure
        * **<delete>** : reset camera

    Examples
    --------
    >>> import numpy as np
    >>> from visbrain.objects import SourceObj
    >>> n_sources = 100
    >>> pos = np.random.uniform(-10, 10, (n_sources, 3))
    >>> color = ['orange'] * 50 + ['red'] * 50
    >>> data = np.random.rand(n_sources)
    >>> text = ['s' + str(k) for k in range(n_sources)]
    >>> s = SourceObj('test', pos, color=color, data=data, radius_min=10.,
    >>>               radius_max=20., edge_color='black', edge_width=1.,
    >>>               text=text, text_size=10.)
    >>> s.preview(axis=True)
    """

    ###########################################################################
    ###########################################################################
    #                                BUILT IN
    ###########################################################################
    ###########################################################################

    def __init__(self, name, xyz, data=None, color='red', alpha=1.,
                 symbol='disc', radius_min=5., radius_max=10., edge_width=0.,
                 edge_color='black', system='mni', mask=None,
                 mask_color='gray', text=None, text_size=2.,
                 text_color='white', text_bold=False,
                 text_translate=(0., 2., 0.), visible=True, transform=None,
                 parent=None, verbose=None, _z=-10., **kw):
        """Init."""
        # VisbrainObject.__init__(self, name, parent, transform, verbose, **kw)
        # _______________________ CHECKING _______________________
        # XYZ :
        sh = xyz.shape
        assert sh[1] in [2, 3]
        self._n_sources = sh[0]
        pos = xyz if sh[1] == 3 else np.c_[xyz, np.full((len(self),), _z)]
        # Radius min and max :
        assert all([isinstance(k, (int, float)) for k in (
            radius_min, radius_max)])
        radius_max = max(radius_min, radius_max)
        self._radius_min, self._radius_max = radius_min, radius_max
        # Data :
        if data is None:
            data = np.ones((len(self),))
        else:
            data = np.asarray(data).ravel()
            assert len(data) == len(self)
        self._data = vispy_array(data)
        # System :
        self._xyz = vispy_array(pos)
        # Color :
        self._color = color
        # Edges :
        self._edge_color, self._edge_width = edge_color, edge_width
        # Mask :
        if mask is None:
            mask = [False] * len(self)
        self._mask = np.asarray(mask).ravel().astype(bool)
        assert len(self._mask) == len(self)
        self._mask_color = color2vb(mask_color)
        # Text :
        self._text_size = text_size
        self._text_color = text_color
        self._text_translate = text_translate

        # _______________________ MARKERS _______________________
        self._sources = visuals.Markers(pos=self._xyz, name='Markers',
                                        edge_color=edge_color,
                                        edge_width=edge_width,
                                        symbol=symbol, parent=None)

        # _______________________ TEXT _______________________
        tvisible = text is None
        self._text = [''] * len(self) if tvisible else text
        self._text = np.array(self._text)
        assert len(self._text) == len(self)
        self._sources_text = visuals.Text(self._text, pos=self._xyz,
                                          bold=text_bold, name='Text',
                                          color=color2vb(text_color),
                                          font_size=text_size,
                                          parent=None)
        self._sources_text.visible = not tvisible
        tr = vist.STTransform(translate=text_translate)
        self._sources_text.transform = tr

        # _______________________ UPDATE _______________________
        # Radius / color :
        self.visible = visible
        self._update_radius()
        self._update_color()
        self.alpha = alpha

    def __len__(self):
        """Get the number of sources."""
        return self._n_sources

    def __bool__(self):
        """Return if all source are visible."""
        return np.all(self._visible)

    def __iter__(self):
        """Loop over visible xyz coordinates.

        At each step, the coordinates are (1, 3) and not (3,).
        """
        xyz = self.xyz  # get only visible coordinates
        for k in range(xyz.shape[0]):
            yield xyz[[k], :]

    def __add__(self, value):
        """Add two SourceObj instances.

        This method return a SourceObj with xyz coodinates and the
        source's data but only for visible sources;
        """
        assert isinstance(value, SourceObj)
        name = self._name + ' + ' + value._name
        xyz = np.r_[self._xyz, value._xyz]
        data = np.r_[self._data, value._data]
        text = np.r_[self._text, value._text]
        visible = np.r_[self._visible, value.visible]
        return SourceObj(name, xyz, data=data, text=text, visible=visible)

    ###########################################################################
    ###########################################################################
    #                                UPDATE
    ###########################################################################
    ###########################################################################

    def update(self):
        """Update the source object."""
        self._sources._vbo.set_data(self._sources._data)
        self._sources.update()
        self._sources_text.update()

    def _update_radius(self):
        """Update marker's radius."""
        logger.debug("Weird edge arround markers (source_obj.py)")
        if np.unique(self._data).size == 1:
            radius = self._radius_min * np.ones((len(self,)))
        else:
            radius = normalize(self._data.copy(), tomin=self._radius_min,
                               tomax=self._radius_max)
        self._sources._data['a_size'] = radius
        to_hide = self.hide
        # Marker size + egde width = 0 and text='' for hidden sources :
        self._sources._data['a_size'][to_hide] = 0.
        self._sources._data['a_edgewidth'][to_hide] = 0.
        text = np.array(self._text.copy())
        text[to_hide] = ''
        self._sources_text.text = text
        self.update()

    def _update_color(self):
        """Update marker's color."""
        # Get marker's background color :
        if isinstance(self._color, str):   # color='white'
            bg_color = color2vb(self._color, length=len(self))
        elif isinstance(self._color, list):  # color=['white', 'green']
            assert len(self._color) == len(self)
            bg_color = np.squeeze(np.array([color2vb(k) for k in self._color]))
        elif isinstance(self._color, np.ndarray):  # color = [[0, 0, 0], ...]
            csh = self._color.shape
            assert (csh[0] == len(self)) and (csh[1] >= 3)
            if self._color.shape[1] == 3:  # RGB
                self._color = np.c_[self._color, np.full(len(self),
                                                         self._alpha)]
            bg_color = self._color.copy()
        # Update masked marker's color :
        bg_color[self._mask, :] = self._mask_color
        self._sources._data['a_bg_color'] = bg_color
        self.update()

    def _get_camera(self):
        """Get the most adapted camera."""
        d_mean = self._xyz.mean(0)
        dist = 1.1 * np.linalg.norm(self._xyz, axis=1).max()
        return scene.cameras.TurntableCamera(center=d_mean, scale_factor=dist)

    ###########################################################################
    ###########################################################################
    #                                  PHYSIO
    ###########################################################################
    ###########################################################################

    def color_sources(self, analysis=None, color_by=None, data=None,
                      roi_to_color=None, color_others='black',
                      hide_others=False, cmap='viridis', clim=None, vmin=None,
                      vmax=None, under='gray', over='red'):
        """Custom color sources methods.

        This method can be used to color sources :

            * According to a data vector. In that case, source's colors are
              inferred using colormap inputs (i.e cmap, vmin, vmax, clim, under
              and over)
            * According to ROI analysis (using the `analysis` and `color_by`
              input parameters)

        Parameters
        ----------
        data : array_like | None
            A vector of data with the same length as the number os sources.
            The color is inferred from this data vector and can be controlled
            using the cmap, clim, vmin, vmax, under and over parameters.
        analysis : pandas.DataFrames | None
            ROI analysis runned using the analyse_sources method.
        color_by : string | None
            A column name of the analysis DataFrames. This columns is then used
            to identify the color to set to each source inside ROI.
        roi_to_color : dict | None
            Define custom colors to ROI. For example use {'BA4': 'red',
            'BA32': 'blue'} to define custom colors. If roi_to_color is None,
            random colors will be used instead.
        color_others : array_like/tuple/string | 'black'
            Specify how to color sources that are not found using the
            roi_to_color dictionary.
        hide_others : bool | False
            Show or hide sources that are not found using the
            roi_to_color dictionary.
        """
        if isinstance(data, np.ndarray):
            assert len(data) == len(self) and (data.ndim == 1)
            logger.info("Color %s using a data vector" % self.name)
            kw = self._update_cbar_args(cmap, clim, vmin, vmax, under, over)
            colors = array2colormap(data, **kw)
        elif (analysis is not None) and (color_by is not None):
            # Group analysis :
            assert color_by in list(analysis.columns)
            logger.info("Color %s according to the %s" % (self.name, color_by))
            gp = analysis.groupby(color_by).groups
            # Compute color :
            if roi_to_color is None:  # random color
                # Predefined colors and define unique color for each ROI :
                colors = np.zeros((len(self), 3), dtype=np.float32)
                u_col = np.random.uniform(.1, .8, (len(gp), 3))
                u_col = u_col.astype(np.float32)
                # Assign color to the ROI :
                for k, index in enumerate(gp.values()):
                    colors[list(index), :] = u_col[k, :]
            elif isinstance(roi_to_color, dict):  # user defined colors
                colors = color2vb(color_others, length=len(self))
                keep_visible = np.zeros(len(self), dtype=bool)
                for roi_name, roi_col in roi_to_color.items():
                    if roi_name in list(gp.keys()):
                        colors[list(gp[roi_name]), :] = color2vb(roi_col)
                        keep_visible[list(gp[roi_name])] = True
                    else:
                        warn("%s not found in the %s column of analysis"
                             "." % (roi_name, color_by))
                if hide_others:
                    self.visible = keep_visible
            else:
                raise TypeError("roi_to_color must either be None or a "
                                "dictionary like {'roi_name': 'red'}.")
        self.color = colors

    def set_visible_sources(self, select='all', v=None, distance=5.):
        """Select sources that are either inside or outside the mesh.

        Parameters
        ----------
        select : {'inside', 'outside', 'close', 'all', 'none', 'left', 'right'}
            Custom source selection. Use 'inside' or 'outside' to select
            sources respectively inside or outside the volume. Use 'close' to
            select sources that are closed to the surface (see the distance
            parameter below). Finally, use 'all' (or True), 'none' (or None,
            False) to show or hide all of the sources.
        v : array_like | None
            The vertices of shape (nv, 3) or (nv, 3, 3) if index faced.
        distance : float | 5.
            Distance between the source and the surface.
        """
        select = select.lower() if isinstance(select, str) else select
        assert select in ['all', 'inside', 'outside', 'none', 'close', None,
                          True, False, 'left', 'right']
        assert isinstance(distance, (int, float))
        xyz = self._xyz
        if select in ['inside', 'outside', 'close']:
            logger.info("Select sources %s vertices" % select)
            if v.ndim == 2:  # index faced vertices
                v = v[:, np.newaxis, :]
            # Predifined inside :
            nv, index_faced = v.shape[0], v.shape[1]
            v = v.reshape(nv * index_faced, 3)
            inside = np.ones((xyz.shape[0],), dtype=bool)

            # Loop over ALL oh the sources :
            for i in range(len(self)):
                # Get the euclidian distance :
                eucl = cdist(v, xyz[[i], :])
                # Get the closest vertex :
                eucl_argmin = eucl.argmin()
                # Get distance to zero :
                xyz_t0 = np.sqrt((xyz[[i], :] ** 2).sum())
                v_t0 = np.sqrt((v[eucl_argmin, :] ** 2).sum())
                if select in ['inside', 'outside']:
                    inside[i] = xyz_t0 <= v_t0
                elif select == 'close':
                    inside[i] = np.abs(xyz_t0 - v_t0) > distance
            self.visible = inside if select == 'inside' else np.invert(inside)
        elif select in ['all', 'none', None, True, False]:
            cond = select in ['all', True]
            self.visible = cond
            self.visible_obj = cond
            msg = 'Display' if cond else 'Hide'
            logger.info("%s all sources" % msg)
        elif select in ['left', 'right']:
            logger.info('Select sources in the %s hemisphere' % select)
            vec = xyz[:, 0]
            self.visible = vec <= 0 if select == 'left' else vec >= 0

    def fit_to_vertices(self, v):
        """Move sources to the closest vertex.

        Parameters
        ----------
        v : array_like
            The vertices of shape (nv, 3) or (nv, 3, 3) if index faced.
        """
        if v.ndim == 2:  # index faced vertices
            v = v[:, np.newaxis, :]
        # Predifined inside :
        nv, index_faced = v.shape[0], v.shape[1]
        v = v.reshape(nv * index_faced, 3)
        new_pos = np.zeros_like(self._xyz)

        # Loop over visible and not-masked sources :
        for i, k in enumerate(self):
            # Get the euclidian distance :
            eucl = cdist(v, k)
            # Set new coordinate using the closest vertex :
            new_pos[i, :] = v[eucl.argmin(), :]
        # Finally update data sources and text :
        self._sources._data['a_position'] = new_pos
        self._sources_text.pos = new_pos
        self.update()

    ###########################################################################
    ###########################################################################
    #                             PROPERTIES
    ###########################################################################
    ###########################################################################

    # ----------- XYZ -----------
    @property
    def xyz(self):
        """Get the visible xyz value."""
        return self._xyz[self.visible_and_not_masked]

    # ----------- DATA -----------
    @property
    def data(self):
        """Get the data value."""
        return self._data[self.visible_and_not_masked]

    @data.setter
    @wrap_properties
    def data(self, value):
        """Set data value."""
        assert isinstance(value, np.ndarray) and len(value) == len(self)
        self._data = value

    # ----------- TEXT -----------
    @property
    def text(self):
        """Get the text value."""
        return np.array(self._text)[self.visible_and_not_masked]

    @text.setter
    @wrap_properties
    def text(self, value):
        """Set text value."""
        assert len(value) == len(self._text)
        self._text = value
        self._sources_text.visible = True
        self._update_radius()

    # ----------- VISIBLE_AND_NOT_MASKED -----------
    @property
    def visible_and_not_masked(self):
        """Get the visible_and_not_masked value."""
        return np.logical_and(self._visible, ~self.mask)

    # ----------- RADIUSMIN -----------
    @property
    def radius_min(self):
        """Get the radius_min value."""
        return self._radius_min

    @radius_min.setter
    @wrap_properties
    def radius_min(self, value):
        """Set radius_min value."""
        assert isinstance(value, (int, float))
        self._radius_min = min(self._radius_max, value)
        self._update_radius()

    # ----------- RADIUSMAX -----------
    @property
    def radius_max(self):
        """Get the radius_max value."""
        return self._radius_max

    @radius_max.setter
    @wrap_properties
    def radius_max(self, value):
        """Set radius_max value."""
        assert isinstance(value, (int, float))
        self._radius_max = max(self._radius_min, value)
        self._update_radius()

    # ----------- SYMBOL -----------
    @property
    def symbol(self):
        """Get the symbol value."""
        return self._sources.symbol

    @symbol.setter
    @wrap_properties
    def symbol(self, value):
        """Set symbol value."""
        assert isinstance(value, str)
        self._sources.symbol = value
        self._sources.update()

    # ----------- EDGE_WIDTH -----------
    @property
    def edge_width(self):
        """Get the edge_width value."""
        return self._edge_width

    @edge_width.setter
    @wrap_properties
    def edge_width(self, value):
        """Set edge_width value."""
        assert isinstance(value, (int, float))
        self._edge_width = value
        self._sources._data['a_edgewidth'] = value
        self.update()

    # ----------- EDGE_COLOR -----------
    @property
    def edge_color(self):
        """Get the edge_color value."""
        return self._edge_color

    @edge_color.setter
    @wrap_properties
    def edge_color(self, value):
        """Set edge_color value."""
        color = color2vb(value, alpha=self.alpha)
        self._sources._data['a_fg_color'] = color
        self._edge_color = color
        self.update()

    # ----------- ALPHA -----------
    @property
    def alpha(self):
        """Get the alpha value."""
        return self._alpha

    @alpha.setter
    @wrap_properties
    def alpha(self, value):
        """Set alpha value."""
        assert isinstance(value, (int, float))
        assert 0 <= value <= 1
        self._alpha = value
        self._sources._data['a_fg_color'][:, -1] = value
        self._sources._data['a_bg_color'][:, -1] = value
        self.update()

    # ----------- COLOR -----------
    @property
    def color(self):
        """Get the color value."""
        return self._color

    @color.setter
    @wrap_properties
    def color(self, value):
        """Set color value."""
        self._color = value
        self._update_color()

    # ----------- MASK -----------
    @property
    def mask(self):
        """Get the mask value."""
        return self._mask

    @mask.setter
    @wrap_properties
    def mask(self, value):
        """Set mask value."""
        assert len(value) == len(self)
        self._mask = value
        self._update_color()

    # ----------- IS_MASKED -----------
    @property
    def is_masked(self):
        """Get the is_masked value."""
        return any(self._mask)

    # ----------- MASKCOLOR -----------
    @property
    def mask_color(self):
        """Get the mask_color value."""
        return self._mask_color

    @mask_color.setter
    @wrap_properties
    def mask_color(self, value):
        """Set mask_color value."""
        self._mask_color = color2vb(value)
        self._update_color()

    # ----------- VISIBLE -----------
    @property
    def visible(self):
        """Get the visible value."""
        return self._visible

    @visible.setter
    @wrap_properties
    def visible(self, value):
        """Set visible value."""
        if isinstance(value, bool):
            self._visible = np.full((len(self),), value)
        else:
            self._visible = np.asarray(value).ravel().astype(bool)
        assert len(self._visible) == len(self)
        self._update_radius()

    # ----------- HIDE -----------
    @property
    def hide(self):
        """Get the hide value."""
        return np.invert(self._visible)

    # ----------- TEXT_SIZE -----------
    @property
    def text_size(self):
        """Get the text_size value."""
        return self._text_size

    @text_size.setter
    @wrap_properties
    def text_size(self, value):
        """Set text_size value."""
        assert isinstance(value, (int, float))
        self._text_size = value
        self._sources_text.font_size = value
        self._sources_text.update()

    # ----------- TEXT_COLOR -----------
    @property
    def text_color(self):
        """Get the text_color value."""
        return self._text_color

    @text_color.setter
    @wrap_properties
    def text_color(self, value):
        """Set text_color value."""
        color = color2vb(value)
        self._sources_text.color = color
        self._text_color = color
        self._sources_text.update()

    # ----------- TEXT_TRANSLATE -----------
    @property
    def text_translate(self):
        """Get the text_translate value."""
        return self._text_translate

    @text_translate.setter
    @wrap_properties
    def text_translate(self, value):
        """Set text_translate value."""
        assert len(value) == 3
        self._sources_text.transform.translate = value
        self._text_translate = value
        self._sources_text.update()
