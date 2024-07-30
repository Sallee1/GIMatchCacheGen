python -m venv env
.\env\Scripts\activate.ps1
pip install -r requirements.txt

git clone --recursive git@github.com:opencv/opencv-python.git -b 84 --depth=1 
cd opencv-python
$env:CMAKE_ARGS = "-DOPENCV_ENABLE_NONFREE=ON -DENABLE_CONTRIB=1 -DOPENCV_EXTRA_MODULES_PATH=../../../opencv_contrib/modules/"
python setup.py bdist_wheel
cd dist
pip install .\opencv_python-4.10.0.84-cp310-cp310-win_amd64.whl