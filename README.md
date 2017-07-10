# hou_farm
A Deadline farm submission tool.

For a short blog post with screen shots, go here: http://www.andynicholas.com/?p=1877

## Features

  * Do away with the cluttered and over-complicated submission dialog. Instead, it places all the submission settings on the ROP nodes. This saves having to remember the settings for each ROP task that you submit to the farm.
  * Hides many of the less common Deadline settings under an Advanced section (hidden by default)
  * Supports the following ROPs (not all fully tested yet, although they should be fine):
    * Mantra ROP
    * Geometry ROP (and SOP version)
    * Alembic ROP
    * IFD Archive ROP
    * Comp ROP
    * Channel ROP
    * BakeTexture ROP
    * OpenGL ROP
    * DOP ROP
  * Respects simple dependency indicated by ROP tree network. Creates jobs on a ROP by ROP basis, and does not split into individual frame dependencies.
  * Allows submission of:
    * Individual nodes
    * Nodes above the submitted ROP node
    * The entire connected ROP tree.
  * Shelf tool patches existing ROP nodes with settings. No custom nodes
  * Deadline interface for the nodes is built on the fly from config file. Easy to reuse parameter layouts and add new nodes.
  * Allows you to split tasks into N chunks, or automatically calculate number of chunks based on number of frames.
  * Performs validation of ROP nodes before submission and reports errors and warnings. For example, it catches common errors such as:
    * Missing camera
    * Disabled IFD export
    * Using default IFD path
    * Missing specified Deadline pool
    * Camera background image enabled
  * Gracefull fallback should hou_farm or Deadline not be present on the system. Won't break your scene or generate annoying errors.
  * Allows you to develop/test Hou Farm without Deadline installed by defining HOUFARM_VIRTUAL_DEADLINE in the environment.

## Installation

  1) Open hou_farm_example.env and copy the lines into your own $HOME/houdini/XX.Y/houdini.env file. 
  1) Change the HOUFARM environment variable to point to the location of hou_farm.
  1) Launch Houdini.
  1) Add the hou_farm shelf to your toolbar at the top by clicking on the + button and selecting Shelves->Hou Farm.

## Usage
  1) Now that hou_farm is installed you should be able to select ROPs in the network view and use the hou_farm "Patch" shelf tool to add the settings to the ROPs.
  1) Patching a node puts all existing parameters under a top-level folder, and creates a new folder called Deadline where you can find all the submission settings.
  1) When you first do this in a session of Houdini, hou_farm will cache the Deadline pools and groups to save having to re-interrogate the Deadline database everytime you select a new node. If you need to update the lists, then go to the Settings tab and click on "Refresh Pools/Groups".
  1) Once you're happy with the settings, just click on the appropriate Submit button to send the scene to the farm.

## Future Work

  * Better usage documentation
  * Provide checkboxes to allow validation tests to be enabled/disabled.
  * Add support for custom validation python code.
  * Support Fetch ROP
  * Add Wedge functionality (possibly through custom ROP rather than existing Wedge ROP)

## Development Notes

  * Only tested on Windows so far. In theory, it should work fine on Linux and OSX, although I'm sure there'll be some fixes required.
  * Mostly written a functional style, and relatively little OOP. This was done mainly because I've been using OOP for a long time and after working on a pure C project, I wanted to experiment with seeing how necessary OOP actually is. Sometimes OOP just gets in the way. May decide at some point to rework some of this into classes to reduce code bloat.
  * Hou_farm was written to potentially expand to support other farm software. It would still need a lot of factorisation for better reuse of much of the Deadline code.
  * There's a makefile for generating code documentation using Sphynx in the docs folder.
  
  
  
