# stamp
Simple tk inter app to log your time in a database. Stamp in and out with a code and comment. defaults can be modified in defaults.yaml.

# install dependencies
```bash
conda env create -f environment.yaml env create -f environment.yaml
```

# run
```bash
conda run -n timekeeper python stamp_app.py"
```

# desktop app (Ubuntu)
change the two paths in stamp.desktop to match your environment under "exec"
```bash
chmod +x stamp.desktop
cp desktop_app/stamp.desktop ~/.local/share/applications/stamp.desktop
```
dekstop icon must be placed on dekstop and then "allow launching" before use
icon can now be dragged to your app band for easy access
reboot might be necesary to flush the changes...
