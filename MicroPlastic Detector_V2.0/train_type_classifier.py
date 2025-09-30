import tensorflow as tf
from tensorflow.keras import layers, models
import os
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix
import json
import datetime

# -------- SETTINGS --------
DATA_DIR = "dataset"   # your dataset root folder
IMG_SIZE = (128, 128)
BATCH_SIZE = 32
EPOCHS = 20
FINE_TUNE_EPOCHS = 10
MODEL_OUT = "microplastic_type_model"
VALIDATION_SPLIT = 0.2
SAVE_PLOTS = True
PLOT_DIR = "training_plots"
# --------------------------

def create_directories():
    """Create necessary directories"""
    for dir_path in [MODEL_OUT, PLOT_DIR]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"Created directory: {dir_path}")

def validate_dataset_structure():
    """Validate dataset structure and provide feedback"""
    train_dir = os.path.join(DATA_DIR, "train")
    val_dir = os.path.join(DATA_DIR, "val")
    
    if not os.path.exists(train_dir):
        raise FileNotFoundError(f"Training directory not found: {train_dir}")
    
    if not os.path.exists(val_dir):
        print(f"Warning: Validation directory not found: {val_dir}")
        print("Will use validation_split from training data")
    
    # Count samples per class
    class_counts = {}
    for class_dir in os.listdir(train_dir):
        class_path = os.path.join(train_dir, class_dir)
        if os.path.isdir(class_path):
            count = len([f for f in os.listdir(class_path) 
                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))])
            class_counts[class_dir] = count
    
    print("\n=== Dataset Overview ===")
    total_samples = sum(class_counts.values())
    print(f"Total training samples: {total_samples}")
    print("Samples per class:")
    for class_name, count in class_counts.items():
        percentage = (count / total_samples) * 100
        print(f"  {class_name}: {count} ({percentage:.1f}%)")
    
    # Check for class imbalance
    if class_counts:
        max_count = max(class_counts.values())
        min_count = min(class_counts.values())
        imbalance_ratio = max_count / min_count if min_count > 0 else float('inf')
        
        if imbalance_ratio > 5:
            print(f"\nWarning: Class imbalance detected (ratio: {imbalance_ratio:.1f}:1)")
            print("Consider using class weights or data augmentation")
    
    return class_counts

def load_datasets():
    """Load datasets with enhanced error handling"""
    try:
        # Load training dataset
        train_ds = tf.keras.preprocessing.image_dataset_from_directory(
            os.path.join(DATA_DIR, "train"),
            image_size=IMG_SIZE,
            batch_size=BATCH_SIZE,
            label_mode="categorical",
            validation_split=VALIDATION_SPLIT,
            subset="training",
            seed=42
        )
        
        # Try to load separate validation set, fallback to split
        val_dir = os.path.join(DATA_DIR, "val")
        if os.path.exists(val_dir) and len(os.listdir(val_dir)) > 0:
            val_ds = tf.keras.preprocessing.image_dataset_from_directory(
                val_dir,
                image_size=IMG_SIZE,
                batch_size=BATCH_SIZE,
                label_mode="categorical"
            )
            print("Using separate validation dataset")
        else:
            val_ds = tf.keras.preprocessing.image_dataset_from_directory(
                os.path.join(DATA_DIR, "train"),
                image_size=IMG_SIZE,
                batch_size=BATCH_SIZE,
                label_mode="categorical",
                validation_split=VALIDATION_SPLIT,
                subset="validation",
                seed=42
            )
            print(f"Using {VALIDATION_SPLIT*100}% of training data for validation")
        
        return train_ds, val_ds
    
    except Exception as e:
        print(f"Error loading datasets: {e}")
        print("Please ensure your dataset structure is:")
        print("dataset/")
        print("  train/")
        print("    class1/")
        print("    class2/")
        print("  val/ (optional)")
        print("    class1/")
        print("    class2/")
        raise

def create_enhanced_augmentation():
    """Create enhanced data augmentation pipeline"""
    return tf.keras.Sequential([
        layers.RandomFlip("horizontal_and_vertical"),
        layers.RandomRotation(0.3),
        layers.RandomZoom(0.2),
        layers.RandomContrast(0.2),
        layers.RandomBrightness(0.1),
        layers.RandomTranslation(0.1, 0.1),
    ])

def build_model(num_classes, input_shape):
    """Build the model with enhanced architecture"""
    # Base model
    base_model = tf.keras.applications.MobileNetV2(
        input_shape=input_shape,
        include_top=False,
        weights="imagenet"
    )
    base_model.trainable = False
    
    # Data augmentation
    data_augmentation = create_enhanced_augmentation()
    
    # Build model
    inputs = layers.Input(shape=input_shape)
    x = data_augmentation(inputs)
    x = tf.keras.applications.mobilenet_v2.preprocess_input(x)
    x = base_model(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(256, activation="relu")(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.5)(x)
    outputs = layers.Dense(num_classes, activation="softmax")(x)
    
    model = models.Model(inputs, outputs)
    return model, base_model

def calculate_class_weights(train_ds):
    """Calculate class weights for imbalanced datasets"""
    try:
        # Extract labels from dataset
        labels = []
        for _, label_batch in train_ds:
            labels.extend(np.argmax(label_batch.numpy(), axis=1))
        
        # Calculate class weights
        from sklearn.utils.class_weight import compute_class_weight
        classes = np.unique(labels)
        class_weights = compute_class_weight(
            'balanced',
            classes=classes,
            y=labels
        )
        
        class_weight_dict = dict(zip(classes, class_weights))
        print("\nClass weights:")
        for class_idx, weight in class_weight_dict.items():
            print(f"  Class {class_idx}: {weight:.3f}")
        
        return class_weight_dict
    
    except Exception as e:
        print(f"Warning: Could not calculate class weights: {e}")
        return None

def create_callbacks(model_path):
    """Create enhanced training callbacks"""
    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            filepath=os.path.join(model_path, "best_weights.h5"),
            monitor='val_accuracy',
            save_best_only=True,
            save_weights_only=True,
            verbose=1
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.2,
            patience=3,
            min_lr=1e-7,
            verbose=1
        ),
        tf.keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=5,
            restore_best_weights=True,
            verbose=1
        ),
        tf.keras.callbacks.CSVLogger(
            os.path.join(model_path, 'training_log.csv'),
            append=True
        )
    ]
    
    return callbacks

def plot_training_history(history, fine_tune_history=None, save_path=None):
    """Plot and save training history"""
    if not SAVE_PLOTS:
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # Combine histories if fine-tuning was performed
    if fine_tune_history is not None:
        epochs1 = len(history.history['accuracy'])
        epochs2 = len(fine_tune_history.history['accuracy'])
        
        acc = history.history['accuracy'] + fine_tune_history.history['accuracy']
        val_acc = history.history['val_accuracy'] + fine_tune_history.history['val_accuracy']
        loss = history.history['loss'] + fine_tune_history.history['loss']
        val_loss = history.history['val_loss'] + fine_tune_history.history['val_loss']
        
        epochs = range(1, len(acc) + 1)
    else:
        acc = history.history['accuracy']
        val_acc = history.history['val_accuracy']
        loss = history.history['loss']
        val_loss = history.history['val_loss']
        epochs = range(1, len(acc) + 1)
        epochs1 = len(acc)
        epochs2 = 0
    
    # Plot accuracy
    axes[0, 0].plot(epochs, acc, 'b-', label='Training Accuracy')
    axes[0, 0].plot(epochs, val_acc, 'r-', label='Validation Accuracy')
    if epochs2 > 0:
        axes[0, 0].axvline(x=epochs1, color='g', linestyle='--', alpha=0.7, label='Fine-tuning Start')
    axes[0, 0].set_title('Model Accuracy')
    axes[0, 0].set_xlabel('Epoch')
    axes[0, 0].set_ylabel('Accuracy')
    axes[0, 0].legend()
    axes[0, 0].grid(True)
    
    # Plot loss
    axes[0, 1].plot(epochs, loss, 'b-', label='Training Loss')
    axes[0, 1].plot(epochs, val_loss, 'r-', label='Validation Loss')
    if epochs2 > 0:
        axes[0, 1].axvline(x=epochs1, color='g', linestyle='--', alpha=0.7, label='Fine-tuning Start')
    axes[0, 1].set_title('Model Loss')
    axes[0, 1].set_xlabel('Epoch')
    axes[0, 1].set_ylabel('Loss')
    axes[0, 1].legend()
    axes[0, 1].grid(True)
    
    # Plot learning rate if available
    if 'lr' in history.history:
        lr = history.history['lr']
        if fine_tune_history and 'lr' in fine_tune_history.history:
            lr += fine_tune_history.history['lr']
        
        axes[1, 0].plot(epochs, lr, 'g-', label='Learning Rate')
        axes[1, 0].set_title('Learning Rate Schedule')
        axes[1, 0].set_xlabel('Epoch')
        axes[1, 0].set_ylabel('Learning Rate')
        axes[1, 0].set_yscale('log')
        axes[1, 0].legend()
        axes[1, 0].grid(True)
    else:
        axes[1, 0].text(0.5, 0.5, 'Learning Rate\nNot Available', 
                       ha='center', va='center', transform=axes[1, 0].transAxes)
    
    # Plot accuracy difference
    acc_diff = [val - train for val, train in zip(val_acc, acc)]
    axes[1, 1].plot(epochs, acc_diff, 'purple', label='Val - Train Accuracy')
    axes[1, 1].axhline(y=0, color='black', linestyle='-', alpha=0.3)
    if epochs2 > 0:
        axes[1, 1].axvline(x=epochs1, color='g', linestyle='--', alpha=0.7, label='Fine-tuning Start')
    axes[1, 1].set_title('Overfitting Monitor')
    axes[1, 1].set_xlabel('Epoch')
    axes[1, 1].set_ylabel('Accuracy Difference')
    axes[1, 1].legend()
    axes[1, 1].grid(True)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(os.path.join(save_path, 'training_history.png'), dpi=300, bbox_inches='tight')
        print(f"Training plots saved to {save_path}/training_history.png")
    
    plt.show()

def evaluate_model(model, val_ds, class_names, save_path=None):
    """Comprehensive model evaluation"""
    print("\n=== Model Evaluation ===")
    
    # Get predictions
    y_true = []
    y_pred = []
    
    for images, labels in val_ds:
        predictions = model.predict(images, verbose=0)
        y_true.extend(np.argmax(labels.numpy(), axis=1))
        y_pred.extend(np.argmax(predictions, axis=1))
    
    # Classification report
    report = classification_report(y_true, y_pred, target_names=class_names, 
                                 output_dict=True, zero_division=0)
    print("\nClassification Report:")
    print(classification_report(y_true, y_pred, target_names=class_names, zero_division=0))
    
    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    
    if SAVE_PLOTS and save_path:
        # Plot confusion matrix
        plt.figure(figsize=(10, 8))
        plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
        plt.title('Confusion Matrix')
        plt.colorbar()
        tick_marks = np.arange(len(class_names))
        plt.xticks(tick_marks, class_names, rotation=45)
        plt.yticks(tick_marks, class_names)
        
        # Add text annotations
        thresh = cm.max() / 2.
        for i, j in np.ndindex(cm.shape):
            plt.text(j, i, format(cm[i, j], 'd'),
                    ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black")
        
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')
        plt.tight_layout()
        plt.savefig(os.path.join(save_path, 'confusion_matrix.png'), dpi=300, bbox_inches='tight')
        plt.show()
        
        # Save evaluation report
        with open(os.path.join(save_path, 'evaluation_report.json'), 'w') as f:
            json.dump(report, f, indent=2)
    
    return report

def save_model_info(model, class_names, save_path, training_config):
    """Save comprehensive model information"""
    model_info = {
        'model_architecture': 'MobileNetV2 + Custom Head',
        'input_shape': list(IMG_SIZE) + [3],
        'num_classes': len(class_names),
        'class_names': class_names,
        'training_config': training_config,
        'creation_date': datetime.datetime.now().isoformat(),
        'framework': 'TensorFlow ' + tf.__version__
    }
    
    # Save model info
    with open(os.path.join(save_path, 'model_info.json'), 'w') as f:
        json.dump(model_info, f, indent=2)
    
    # Save model summary
    with open(os.path.join(save_path, 'model_summary.txt'), 'w') as f:
        model.summary(print_fn=lambda x: f.write(x + '\n'))
    
    print(f"Model information saved to {save_path}")

def main():
    """Main training pipeline"""
    print("=== Enhanced Microplastic Type Classifier Training ===")
    
    # Create directories
    create_directories()
    
    # Validate dataset
    class_counts = validate_dataset_structure()
    
    # Load datasets
    train_ds, val_ds = load_datasets()
    
    class_names = train_ds.class_names
    num_classes = len(class_names)
    print(f"\nTraining classes: {class_names}")
    
    # Optimize dataset performance
    AUTOTUNE = tf.data.AUTOTUNE
    train_ds = train_ds.shuffle(1000).cache().prefetch(AUTOTUNE)
    val_ds = val_ds.cache().prefetch(AUTOTUNE)
    
    # Calculate class weights
    class_weights = calculate_class_weights(train_ds)
    
    # Build model
    model, base_model = build_model(num_classes, IMG_SIZE + (3,))
    
    # Compile model
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-4),
        loss="categorical_crossentropy",
        metrics=["accuracy"]
    )
    
    print("\n=== Model Architecture ===")
    model.summary()
    
    # Training configuration
    training_config = {
        'img_size': IMG_SIZE,
        'batch_size': BATCH_SIZE,
        'epochs': EPOCHS,
        'fine_tune_epochs': FINE_TUNE_EPOCHS,
        'validation_split': VALIDATION_SPLIT,
        'class_weights_used': class_weights is not None,
        'data_augmentation': True
    }
    
    # Create callbacks
    callbacks = create_callbacks(MODEL_OUT)
    
    print("\n=== Starting Initial Training ===")
    # Initial training
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=EPOCHS,
        callbacks=callbacks,
        class_weight=class_weights,
        verbose=1
    )
    
    print("\n=== Starting Fine-tuning ===")
    # Fine-tuning
    base_model.trainable = True
    fine_tune_at = 100
    
    for layer in base_model.layers[:fine_tune_at]:
        layer.trainable = False
    
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-5),
        loss="categorical_crossentropy",
        metrics=["accuracy"]
    )
    
    # Fine-tune with reduced learning rate
    fine_tune_history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=FINE_TUNE_EPOCHS,
        callbacks=callbacks,
        class_weight=class_weights,
        verbose=1
    )
    
    # Load best weights
    model.load_weights(os.path.join(MODEL_OUT, "best_weights.h5"))
    
    print("\n=== Training Complete ===")
    
    # Plot training history
    plot_training_history(history, fine_tune_history, PLOT_DIR)
    
    # Evaluate model
    evaluation_report = evaluate_model(model, val_ds, class_names, PLOT_DIR)
    
    # Save model and metadata
    model.save(MODEL_OUT)
    
    # Save classes.txt for compatibility
    with open(os.path.join(MODEL_OUT, "classes.txt"), "w") as f:
        for class_name in class_names:
            f.write(class_name + "\n")
    
    # Save comprehensive model information
    save_model_info(model, class_names, MODEL_OUT, training_config)
    
    print(f"\n=== Training Summary ===")
    print(f"Model saved to: {MODEL_OUT}")
    print(f"Classes: {class_names}")
    print(f"Final validation accuracy: {evaluation_report['accuracy']:.4f}")
    print(f"Macro avg F1-score: {evaluation_report['macro avg']['f1-score']:.4f}")
    print(f"Weighted avg F1-score: {evaluation_report['weighted avg']['f1-score']:.4f}")
    
    if SAVE_PLOTS:
        print(f"Plots saved to: {PLOT_DIR}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Training failed: {e}")
        import traceback
        traceback.print_exc()