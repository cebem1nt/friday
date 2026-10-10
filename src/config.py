# TODO config parsing or per chat settings

model = "gemma4:e4b"

voice_model = "/home/cebem1nt/voices/en_US-ljspeech-high.onnx" 

# Size 	  Parameters  English-only model  Multilingual model 	Required VRAM 	Relative speed
# tiny 	    39 M 	     tiny.en 	           tiny 	            ~1 GB 	         ~10x
# base 	    74 M 	     base.en 	           base 	            ~1 GB 	         ~7x
# small 	244 M 	     small.en 	           small 	            ~2 GB 	         ~4x
# medium 	769 M 	     medium.en 	           medium 	            ~5 GB 	         ~2x
# large 	1550 M 	     N/A 	               large 	            ~10 GB 	         1x
# turbo 	809 M 	     N/A 	               turbo 	            ~6 GB 	         ~8x

whisper_model = "small.en"

rich_formatting = True