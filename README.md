matlib
===

Blender Addon. This is not a Material Library. It is a Materials Librarian.


The name of a material is how it is retrieved, and the librarian will ask for confirmation before putting duplicates or allow you to rename.  Best usage pattern is to give a good name and then send to the library.Names like 'Material' or 'asdf.001' are not very helpful anyway.


Materials are stored in blend files which reside in a 'Library Path'.  You'll have to choose a library path.  You may choose more than one, and switch between them.

Hold shift while choosing a Library to open it in a file browser.

Hold alt while choosing a Library to remove it from from the consideration of the librarian.  The path is not deleted.

The materials catalog is made at blender startup, thus the way to delete materials from a library is to delete the blend file which contains it, and then restart blender or reload addons (f8).

The librarian likes to keep one material per blend and name the blend after the material but blends with multiple materials are fine. Be cautious not to delete more than you intend, if you have materials stored more than one-per-blend.

When loading a material, the librarian doesn't care if you already have that identical material loaded already.  You'll get lots of Material.001 type names if you aren't careful.


Matlib Interface
===

The three dots on the Material Properties Header is what you click to show the menu.

