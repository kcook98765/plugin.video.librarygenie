Wellcome to PyXBMCt documentation!¶

PyXBMCt is a Python micro-framework created to simplify creating GUI for Kodi (XBMC) mediacenter addons. It was inspired by PyQt (hence the name) and shares the same basic principles, so those who are familiar with PyQt/PySide should feel themselves right at home.

The framework provides 4 base container classes, 9 ready-to-use widgets or, in Kodi terms, controls, a Grid layout manager and an event connection manager.

PyXBMCt uses texture images from Kodi’s default Confluence and Estuary (Kodi 17 “Krypton” and above) skins to decorate its visual elements. Those textures are included in PyXBMCt, so UI based on it will have the same look in different skins.

PyXBMCt is essentially a thin wrapper around several xbmcgui classes so please consult xbmcgui module documentation on how to use all features of PyXBMCt windows and controls.

PyXBMCt does not provide as many features and customization capabilites as skined GUIs based on xbmcgui.WindowXML and xbmcgui.WindowXMLDialog classes but it is relatively easy to learn and does not require the knowledge of Kodi skinning. PyXBMCt-based GUIs can be created entirely in Python.


Base Classes¶

PyXBMCt provides 4 base classes: AddonDialogWindow, AddonFullWindow, BlankDialogWindow and BlankFullWindow. These classes serve as containers for other UI elements (controls). All base classes are “new-style” Python classes.
AddonDialogWindow

AddonDialogWindow class is based on xbmcgui.WindowDialog and provides an interface window with background and a title-bar. The window serves as a parent control to other UI controls. Like all the other base classes, AddonDialogWindow has the Grid layout manager to simplify arranging your UI controls and the event connection manager to connect XBMC UI events to functions and methods of your addon.
_images/addon_dialog_window.jpg

AddonDialogWindow parent window

The main control window of AddonDialogWindow is always displayed on top of Kodi UI, even video playback and music visualization, so it’s better suited for addons that are not supposed to play video or music.

Note

Width, height and coordinates (optional) for the control window are specified in Kodi UI coordinate grid pixels.

The default resolution of UI coordinate grid is always 1280x720 regardless of your actual display resolution. This way UI elements have the same visible size no matter what display resolution you use.
AddonFullWindow

AddonFullWinow is based on xbcmgui.Window class. It is similar to AddonDialogWindow and also provides a parent control window for other UI controls. But, unlike AddonDialogWindow, it has a solid main background (for which the default Estuary or Confluence background is used) and can hide under video or music visualization.
_images/addon_full_window.jpg

AddonFullWindow parent control window
BlankDialogWindow and BlankFullWindow

BlankDialogWindow and BlankFullWindow are based on xbmcgui.WindowDialog and xbmcgui.Window respectively. They have no visual elements whatsoever, but, like the 2 previously described classes, they provide the Grid layout and event connection managers.

Those classes are meant for DIY developers who want full control over the visual appearance of their addons.


Controls¶

PyXBMCt provides 9 ready-to-use UI controls that are based on the respective xbmcgui controls with the following differences:

    You don’t need to specify coordinates and size for the controls explicitly. The Grid layout manager takes care of control placement.

    All controls that require textures are provided with default textures (borrowed from Confluence and Estuary skin resources). You can specify your own textures for PyXBMCt controls, but you need to do this through keyword arguments (important!).

    Button caption is center-aligned by default. You can change button caption alignment by providing a necessary alignment parameter through a keyword argument (PyXBMCt already includes symbolic constants for control text alignment). Since all PyXBMCt Controls are subclassed from xbmcgui.Control* classes, you can use all parent xbmcgui classes’ methods to set Control properties.

_images/pyxbmct_controls_confl.jpg

PyXBMCt controls (Confluence-based skin)
_images/pyxbmct_controls_est.jpg

PyXBMCt controls (Estuary-based skin)

Below is the list of PyXBMCt controls with brief descriptions:
Label

Label implements a simple text label much like Tkinter.Label or QLabel.
FadeLabel

FaldeLabel is similar to Label, but a very long text string is auto-scrolled.
TextBox

TextBox shows multiline text. It can autoscroll very long text.
Image

Image control displays images from files (.jpg, .png, .gif). For .gif and .png images transparency is supported, and for .gif animation is shown as well.
Button

Button implements a clickable button. It generates a control event on click.
RadioButton

RadioButton is a 2-state switch. It generates a control event on click.
Edit

Edit implements a text entry field, similar to Tkinter.Entry or QLineEdit. When activated, it opens an on-screen keyboard to enter text.
List

List implements a list of items. The list scrolls when it cannot display all its items within available space. It generates a control event when an item is selected.
Slider

Slider is a control for stepless adjusting some value (e.g. volume level).


Grid Layout¶

The Grid Layout helps to place UI controls within the parent window. It is similar to PyQt’s QGridLayout or Tkniter’s Grid geometry manager. The Grid Layout is implemented through setGeometry and placeControl methods of a base PyXBMCt class.

Warning

Currently PyXBMCt does not support changing window geometry at runtime so you must call setGeometry method only once.

To place a control you simply provide it as the 1st positional argument to placeControl method, and then specify a row and a column for the control as the next arguments, and the control will be placed in a specific grid cell. This eliminates the need to provide exact coordinates for each control and then fine-tune them. If a control needs to occupy several grid cells, you can provide rowspan and/or columspan parameters to specify how many cells it should take.

Note

Row and column numbers start from zero, i.e. the top-left cell will have row# = 0, column# = 0.

The placeControl medhod does not actually check if a control will actually be placed within the parent window. By providing a row and/or a column number which exceeds row and/or column count of the parent window, a control can be placed outside the window, intentionally or unintentionally. You need to check the visual appearance of your addon window and correct positions of controls, if necessary.

The Grid Layout also works with xbmcgui Controls, but when instantiating an xbmcgui Control you need to provide it with fake coordinates and size. Any integer values will do.

Tip

The size and aspect of an individual control can be adjusted with pad_x and pad_y parameters of placeControl method. By default, both padding values equal 5.


Connecting Events¶

Connecting events works similarly to the signal-slot connection mechanism of Qt framework. There are two types of events: Control events (when an on-screen Control, e.g. a button, is actvated) and a keyboard action (when a key bound to an action is pressed). You can connect an event to a function or a method that will be run when the respective event is triggered. The connection mechanism is implemented through connect method of a base PyXBMCt class. This methods takes 2 parameters: an object to be connected (a Control instance or a numeric action code, and a function/method object to be called. For example:

self.connect(self.foo_button, self.on_foo_clicked)

Here self.foo_button is a Button instance and self.on_foo_clicked is some method that needs to be called when a user activates self.foo_button.

Warning

For connection you must provide a function object without brackets (), not a function call. Do not confuse those two!

Similarly to PyQt signal-slot connection, lambda can be used to connect a function/method with arguments known at runtime. For example:

self.connect(self.foo_button, lambda: self.on_foo_clicked('bar', 'spam'))

You can only connect the following controls: Button, RadioButton and List. Other controls do not generate any events, so connecting them won’t have any effect.

The key code ACTION_PREVIOUS_MENU or 10 (bound to ESC key by default) is already connected to the method that closes a current addon window (close), so you cannot connect it to any function/method. Or technically you can, but such connection won’t work. It guarantees that you always have a way to close an active addon window.


Using PyXBMCt In Your Addon¶

PyXBMCt addon module is included in the official Kodi (XBMC) repo. So to use it, first you need to add the following string into <requires> section of your addon.xml:

<import addon="script.module.pyxbmct" />

Then you need to import pyxbmct module into the namespace of your addon:

import pyxbmct


Code Examples¶

Now let’s take a look at some examples. As always, we’ll start with “Hello, World!”.
“Hello, World!” example

The simplest code which will display a window with “Hello, World!” header looks like this:

# Import PyXBMCt module.
import pyxbmct

# Create a window instance.
window = pyxbmct.AddonDialogWindow('Hello, World!')
# Set window width, height and grid resolution.
window.setGeometry(400, 400, 1, 1)
# Show the created window.
window.doModal()
# Delete the window instance when it is no longer used.
del window

If you’ve done everything correctly, you should see a window like the one shown below:
_images/hello_world.jpg

“Hello World!” example

The window Grid has 1 row and 1 column. We haven’t placed any controls on it, but setGeometry method takes at least 4 arguments, so we have provided it dummy values. Also for simplicity’s sake we haven’t used OOP in this example.

Now let’s analyze a more complex example.
Example with interactive controls

First, we need to draft the layout or our UI. You can use a pen and paper or imagine the layout in your head, it does not matter. The following table showsh the draft of the UI layout for our example addon:

Rows\Columns


0


1

0


Image

1

2

3


Name Label


Name Edit

4


“Close” button


“Hello” button

As you can see, our example UI will have 4 rows, 2 columns and 5 controls placed in grid cells. Let’s see how it looks in Python code:

# Import necessary modules
import xbmc
import pyxbmct

# Create a class for our UI
class MyAddon(pyxbmct.AddonDialogWindow):

    def __init__(self, title=''):
        """Class constructor"""
        # Call the base class' constructor.
        super(MyAddon, self).__init__(title)
        # Set width, height and the grid parameters
        self.setGeometry(300, 280, 5, 2)
        # Call set controls method
        self.set_controls()
        # Call set navigation method.
        self.set_navigation()
        # Connect Backspace button to close our addon.
        self.connect(pyxbmct.ACTION_NAV_BACK, self.close)

    def set_controls(self):
        """Set up UI controls"""
        # Image control
        image = pyxbmct.Image('https://peach.blender.org/wp-content/uploads/poster_rodents_small.jpg?3016dc')
        self.placeControl(image, 0, 0, rowspan=3, columnspan=2)
        # Text label
        label = pyxbmct.Label('Your name:')
        self.placeControl(label, 3, 0)
        # Text edit control
        self.name_field = pyxbmct.Edit('')
        self.placeControl(self.name_field, 3, 1)
        # Close button
        self.close_button = pyxbmct.Button('Close')
        self.placeControl(self.close_button, 4, 0)
        # Connect close button
        self.connect(self.close_button, self.close)
        # Hello button.
        self.hello_buton = pyxbmct.Button('Hello')
        self.placeControl(self.hello_buton, 4, 1)
        # Connect Hello button.
        self.connect(self.hello_buton, lambda:
            xbmc.executebuiltin('Notification(Hello {0}!, Welcome to PyXBMCt.)'.format(
                self.name_field.getText())))

    def set_navigation(self):
        """Set up keyboard/remote navigation between controls."""
        self.name_field.controlUp(self.hello_buton)
        self.name_field.controlDown(self.hello_buton)
        self.close_button.controlLeft(self.hello_buton)
        self.close_button.controlRight(self.hello_buton)
        self.hello_buton.setNavigation(self.name_field, self.name_field, self.close_button, self.close_button)
        # Set initial focus.
        self.setFocus(self.name_field)


if __name__ == '__main__':
    myaddon = MyAddon('PyXBMCt Example')
    myaddon.doModal()
    del myaddon

This code should display the following window:
_images/example_ui.jpg

Our example UI

If you enter your name (or any words for that matter) and click “Hello” button, the addon will display a pop-up notification:
_images/pop-up.jpg

The pop-up notification

Two remarks about the code:

    In my example I have used an online URL for the Image control. Paths to image files stored on your local disks can be used as well.

    Note the usage of lambda to connect a function (xbmc.executebuiltin() in this case) with an argument.

Despite being rather simple, this example illustrates main steps of initializing PyXBMCt-based addon UI:

    Set up the geometry and grid of the main window.

    Place UI controls on the grid.

    Connect interactive controls and key actions to functions/methods.

    Set up keyboard/remote navigation between controls.

    Set initial focus on a control (necessary for navigation to work).

PyXBMCt demo addon povides more compherensive example on how to use all PyXBMCt Controls.

API Reference¶

All non-abstract classes are available at package level, for example:

from pyxbmct import AddonDialogWindow, Label, Button

pyxbmct.addonwindow


This module contains all classes and constants of PyXBMCt framework

pyxbmct.addonskin


Classes for defining the appearance of PyXBMCt Windows and Controls