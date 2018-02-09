matlib
===

[Download this zip for easy blender install](https://github.com/dustractor/matlib/releases/download/alpha1/matlib.zip)

---

##### for saving and loading materials #####

The entire interface has been made to fit all upon a single row.  It is comprised of a button to send the current material to the current library, a menu to choose or add library paths, and a menu to choose from materials in the current library.

---

### User Preferences ###

There are options for where the interface is shown:

* Above the material selector  [default]  
* Below the material selector  
* As a standard panel  
* On the Material Specials Menu (this adds zero visual clutter)


There is also an option which allows you to have the path-selector hide *after at least one path has been added as a library.*  This is for the hard-core set-it-and-forget-it types.


---

#### Tips ####

Hold shift while selecting a path to open it in a file browser.

Materials are stored in standard blend files. To remove a material, remove the blend. The process of checking whether blends in the database still exist on the filesystem happens during blender startup and whenever a path is selected via the library path selection menu.


