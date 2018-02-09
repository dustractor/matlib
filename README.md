matlib
===

[Download this zip for easy blender install](https://github.com/dustractor/matlib/releases/download/alpha1/matlib.zip)

---

##### for saving and loading materials #####

The interface is comprised of a button to send the current material to the current library, a menu to choose or add library paths, and a menu to choose from materials in the current library.



---

### User Preferences ###

Since all that fits on a single row, there is the option of where to display the row.

* Above the material selector  
* Below the material selector  
* As a standard panel  
* On the Material Specials Menu (this adds zero visual clutter)

Everybody is going to love the default. (Above)  I just know it.


There is also an option which allows you to have the path-selector hide *after at least one path has been added as a library.*  This is for the hard-core set-it-and-forget-it types.


---

#### Tips ####

Hold shift while selecting a path to open it in a file browser.

Materials are stored in standard blend files. To remove a material, remove the blend. The process of checking whether blends in the database still exist on the filesystem happens during blender startup and whenever a path is selected via the library path selection menu.


