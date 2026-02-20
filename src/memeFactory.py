from meme_generator import get_meme
from loguru import logger

def generate_meme(meme_name,screen_name,timestamp,extent,pic_path_lst=[],texts_lst=[],args={}):
    logger.debug(f'generate_meme: {meme_name} for uid: {screen_name}, pics: {pic_path_lst} ,texts: {texts_lst}')
    if pic_path_lst == [] and texts_lst == []:
        logger.error('pic_path_lst and texts_lst cannot be both empty')
        return None
    savepath = f'lib/{meme_name}/{screen_name}_{timestamp}.{extent}'
    meme = get_meme(meme_name)
    rawpic = meme(images=pic_path_lst, texts=texts_lst, args=args)
    
    with open(savepath, "wb") as f:
        f.write(rawpic.getvalue())
    
    return savepath




