import tensorflow as tf
from model import *
from data_layer import *
from utils import *

tf.flags.DEFINE_string('logdir', '', 'Path to save logs and checkpoints')
tf.flags.DEFINE_string('mode', 'train', 'Mode: train/test')
tf.flags.DEFINE_integer('num_epochs', 50, 'Number of training epochs')
FLAGS = tf.flags.FLAGS

deco_print('Creating Data Layer')
if FLAGS.mode == 'train':
	path = '/vol/Numpy_data_subprime_new'
	dl = DataInRamInputLayer(path=path, mode=FLAGS.mode)
	path_valid = '/vol/Numpy_data_subprime_Val_new'
	dl_valid = DataInRamInputLayer(path=path_valid, mode='valid')
elif FLAGS.mode == 'test':
	path = '/vol/Numpy_data_subprime_Test_new'
	dl = DataInRamInputLayer(path=path, mode=FLAGS.mode)
else:
	raise ValueError('Mode Not Implemented')
deco_print('Data Layer Created')

deco_print('Creating Model')
if FLAGS.mode == 'train':
	config = Config(feature_dim=291, num_category=7, dropout=0.9)
	model = Model(config)
	config_valid = Config(feature_dim=291, num_category=7, dropout=1.0)
	model_valid = Model(config_valid, force_var_reuse=True, is_training=False)
else:
	config = Config(feature_dim=291, num_category=7, dropout=1.0)
	model = Model(config, is_training=False)
deco_print('Read Following Config')
deco_print_dict(vars(config))
deco_print('Model Created')

with tf.Session() as sess:
	saver = tf.train.Saver(max_to_keep=50)
	if tf.train.latest_checkpoint(FLAGS.logdir) is not None:
		saver.restore(sess, tf.train.latest_checkpoint(FLAGS.logdir))
		deco_print('Restored Checkpoint')
	else:
		sess.run(tf.global_variables_initializer())
		deco_print('Random Initialization')

	if FLAGS.mode == 'train':
		deco_print('Executing Training Mode\n')
		tf.summary.scalar(name='loss', tensor=model._loss)
		tf.summary.scalar(name='learning_rate', tensor=model._lr)
		summary_op = tf.summary.merge_all()
		sw = tf.summary.FileWriter(FLAGS.logdir, sess.graph)

		cur_epoch_step = 0
		total_epoch_step_loss = 0.0
		count_epoch_step = 0
		
		for epoch in range(FLAGS.num_epochs):
			epoch_start = time.time()
			total_train_loss = 0.0
			count = 0
			for i, (x, y, info) in enumerate(dl.iterate_one_epoch(model._config.batch_size)):
				feed_dict = {model._x_placeholder:x, model._y_placeholder:y, model._epoch_step:info['epoch_step']}
				loss_i, _ = sess.run(fetches=[model._loss, model._train_op], feed_dict=feed_dict)
				total_train_loss += loss_i
				total_epoch_step_loss += loss_i
				count += 1
				count_epoch_step += 1

				if info['epoch_step'] != cur_epoch_step:
					sm, = sess.run(fetches=[summary_op], feed_dict=feed_dict)
					sw.add_summary(sm, global_step=cur_epoch_step)
					train_epoch_step_loss = total_epoch_step_loss / count_epoch_step
					train_loss_value_epoch_step = summary_pb2.Summary.Value(tag='epoch_step_loss', simple_value=train_epoch_step_loss)
					summary = summary_pb2.Summary(value=[train_loss_value_epoch_step])
					sw.add_summary(summary, global_step=cur_epoch_step)
					sw.flush()
					epoch_last = time.time() - epoch_start
					time_est = epoch_last / (info['idx_file'] + 1) * info['num_file']
					deco_print('Epoch Step Loss: %f, Elapse / Estimate: %.2fs / %.2fs     ' %(train_epoch_step_loss, epoch_last, time_est), end='\r')
					total_epoch_step_loss = 0.0
					count_epoch_step = 0
					cur_epoch_step = info['epoch_step']

			train_loss = total_train_loss / count
			deco_print('Epoch {} Training Loss: {}                              '.format(epoch, train_loss))
			train_loss_value = summary_pb2.Summary.Value(tag='Train_Epoch_Loss', simple_value=train_loss)
			summary = summary_pb2.Summary(value=[train_loss_value])
			sw.add_summary(summary=summary, global_step=epoch)
			sw.flush()
			epoch_end = time.time()
			deco_print('Did Epoch {} In {} Seconds '.format(epoch, epoch_end - epoch_start))
			
			deco_print('Running Validation')
			total_valid_loss = 0.0
			count_valid = 0
			for i, (x, y, _) in enumerate(dl_valid.iterate_one_epoch(model_valid._config.batch_size)):
				feed_dict = {model_valid._x_placeholder:x, model_valid._y_placeholder:y}
				loss_i, = sess.run(fetches=[model_valid._loss], feed_dict=feed_dict)
				total_valid_loss += loss_i
				count_valid += 1
			valid_loss = total_valid_loss / count_valid
			deco_print('Epoch {} Validation Loss: {}'.format(epoch, valid_loss))
			valid_loss_value = summary_pb2.Summary.Value(tag='Train_Epoch_Valid_Loss', simple_value=valid_loss)
			summary = summary_pb2.Summary(value=[valid_loss_value])
			sw.add_summary(summary=summary, global_step=epoch)
			sw.flush()
			deco_print('Saving Epoch Checkpoint\n')
			saver.save(sess, save_path=os.path.join(FLAGS.logdir, 'model-epoch'), global_step=epoch)

	else:
		deco_print('Executing Test Mode\n')
		epoch_start = time.time()
		cur_epoch_step = 0
		total_test_loss = 0.0
		count = 0
		for i, (x, y, info) in enumerate(dl.iterate_one_epoch(model._config.batch_size)):
			feed_dict = {model._x_placeholder:x, model._y_placeholder:y}
			loss_i, = sess.run(fetches=[model._loss], feed_dict=feed_dict)
			total_test_loss += loss_i
			count += 1

			if info['epoch_step'] != cur_epoch_step:
				epoch_last = time.time() - epoch_start
				time_est = epoch_last / (info['idx_file'] + 1) * info['num_file']
				deco_print('Test Loss: %f, Elapse / Estimate: %.2fs / %.2fs     ' %(total_test_loss / count, epoch_last, time_est), end='\r')
				cur_epoch_step = info['epoch_step']

		test_loss = total_test_loss / count
		deco_print('Test Loss: %f' %test_loss)
		with open(os.path.join(FLAGS.logdir, 'loss.txt'), 'w') as f:
			f.write('Test Loss: %f\n' %test_loss)
